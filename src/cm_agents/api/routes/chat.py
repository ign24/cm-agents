"""Chat routes with WebSocket support for real-time communication."""

import asyncio
import json
import logging
import time
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ...agents.strategist import StrategistAgent
from ...models.brand import Brand
from ...services.agent_campaign import OrchestratorCampaignService
from ..config import settings
from ..routes.generate import execute_generation
from ..routes.plans import get_plans_dir
from ..schemas import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
    ContentIntentResponse,
    ContentPlanItemResponse,
    ContentPlanResponse,
    VariantResultResponse,
)
from ..security import RateLimitDep, validate_slug
from ..services.plan_manager import PlanValidationError, plan_manager
from ..websocket.manager import manager

logger = logging.getLogger(__name__)
router = APIRouter()

# Initialize strategist agent
strategist = StrategistAgent(knowledge_dir=Path(settings.KNOWLEDGE_DIR))
orchestrator = OrchestratorCampaignService(knowledge_dir=Path(settings.KNOWLEDGE_DIR))

# In-memory conversation storage (replace with persistent storage later)
conversations: dict[str, list[ChatMessage]] = {}
pending_build_requests: dict[str, str] = {}
session_brands: dict[str, str] = {}

# Limits
MAX_SESSIONS = 500
MAX_MESSAGES_PER_SESSION = 80  # keep last N messages per session
MAX_WS_MESSAGES_PER_MINUTE = 30  # per WebSocket connection
MAX_IMAGES_PER_MESSAGE = 5
MAX_IMAGE_SIZE_B64 = 5 * 1024 * 1024  # 5 MB base64 ≈ 3.75 MB decoded


def _evict_oldest_session() -> None:
    """Drop the oldest session when at capacity to prevent unbounded growth."""
    if len(conversations) >= MAX_SESSIONS:
        oldest = next(iter(conversations))
        conversations.pop(oldest, None)
        pending_build_requests.pop(oldest, None)
        session_brands.pop(oldest, None)


def _trim_conversation(session_id: str) -> None:
    """Keep only the most recent messages to cap memory and context size."""
    msgs = conversations.get(session_id)
    if msgs and len(msgs) > MAX_MESSAGES_PER_SESSION:
        conversations[session_id] = msgs[-(MAX_MESSAGES_PER_SESSION // 2):]


def _is_build_confirmation(content: str) -> bool:
    msg = content.strip().lower()
    confirmations = {
        "/build",
        "ok",
        "dale",
        "aprobado",
        "apruebo",
        "si",
        "sí",
        "genera",
        "ejecuta",
        "adelante",
    }
    return msg in confirmations


async def _run_orchestrator_build(session_id: str, brand_slug: str, user_request: str) -> None:
    """Run real orchestrator build in background and stream status to websocket."""
    await manager.send_to_session(
        session_id,
        {
            "type": "build_started",
            "data": {
                "message": "Orchestrator LLM activado. Ejecutando workers...",
                "brand": brand_slug,
            },
        },
    )

    try:
        result = await asyncio.to_thread(
            orchestrator.run_from_user_input,
            brand_slug,
            user_request,
            None,  # style_ref
            1,  # max_retries
            True,  # require_llm_orchestrator
        )
        artifacts = result.get("artifacts", {})
        worker_plan = artifacts.get("worker_plan", {})
        generated = len([g for g in artifacts.get("generation", []) if "image_path" in g])
        errors = len([g for g in artifacts.get("generation", []) if "error" in g])

        await manager.send_to_session(
            session_id,
            {
                "type": "build_completed",
                "data": {
                    "message": (
                        f"Build completado. Workers: {', '.join(worker_plan.get('sequence', []))}. "
                        f"Imágenes: {generated}. Errores: {errors}."
                    ),
                    "run_id": result.get("run_id"),
                    "run_dir": str(result.get("run_dir")),
                    "generated": generated,
                    "errors": errors,
                    "worker_plan": worker_plan,
                },
            },
        )
    except Exception as e:
        logger.error(f"Orchestrator build failed: {e}", exc_info=True)
        await manager.send_error(session_id, f"Error en build real del orquestador: {e}")


def _load_brand(brand_slug: str | None) -> Brand | None:
    """Load brand from slug."""
    if not brand_slug:
        return None
    brand_path = Path(settings.BRANDS_DIR) / brand_slug
    if not brand_path.exists():
        return None
    try:
        return Brand.load(brand_path)
    except Exception as e:
        logger.warning(f"Failed to load brand {brand_slug}: {e}")
        return None


def _plan_to_response(plan) -> ContentPlanResponse:
    """Convert ContentPlan to API response."""
    return ContentPlanResponse(
        id=plan.id,
        brand=plan.brand,
        intent=ContentIntentResponse(
            objective=plan.intent.objective,
            product=plan.intent.product,
            occasion=plan.intent.occasion,
            tone=plan.intent.tone,
            constraints=plan.intent.constraints,
        ),
        items=[
            ContentPlanItemResponse(
                id=item.id,
                product=item.product,
                size=item.size,
                style=item.style,
                copy_suggestion=item.copy_suggestion,
                reference_query=item.reference_query,
                reference_urls=item.reference_urls,
                variants_count=item.variants_count,
                status=item.status,
                variants=[
                    VariantResultResponse(
                        variant_number=v.variant_number,
                        output_path=v.output_path,
                        cost_usd=v.cost_usd,
                        status=v.status,
                        error=v.error,
                        variation_type=v.variation_type,
                    )
                    for v in item.variants
                ],
                output_path=item.output_path,
            )
            for item in plan.items
        ],
        created_at=plan.created_at,
        approved_at=plan.approved_at,
        estimated_cost=plan.estimated_cost,
    )


@router.post("/chat", response_model=ChatResponse)
async def send_chat_message(request: ChatRequest, _: RateLimitDep):
    """
    Send a chat message and get a response from the StrategistAgent.

    This is the REST API version for simple request/response.
    For streaming responses, use the WebSocket endpoint.
    """
    # Validate brand slug if provided
    if request.brand and not validate_slug(request.brand):
        request.brand = None

    # Load brand if specified
    brand = _load_brand(request.brand)

    # Chat with strategist (brand_slug para resolver products/ y requisitos del pipeline)
    try:
        response_text, plan = strategist.chat(
            message=request.message,
            brand=brand,
            context=None,
            images=request.images if request.images else None,
            brand_slug=request.brand if request.brand else None,
        )
    except Exception as e:
        logger.error(f"StrategistAgent error: {e}")
        response_text = f"Error al procesar tu mensaje: {e}"
        plan = None

    # Build response
    assistant_message = ChatMessage(
        role="assistant",
        content=response_text,
        timestamp=datetime.now(),
    )

    plan_response = _plan_to_response(plan) if plan else None

    return ChatResponse(message=assistant_message, plan=plan_response)


@router.websocket("/ws/chat/{session_id}")
async def websocket_chat(websocket: WebSocket, session_id: str):
    """
    WebSocket endpoint for real-time chat with the StrategistAgent.

    Supports:
    - Streaming responses
    - Progress updates during generation
    - Plan creation and approval
    """
    await manager.connect(websocket, session_id)

    # Initialize conversation if new
    if session_id not in conversations:
        _evict_oldest_session()
        conversations[session_id] = []

    # Per-connection rate limit state
    _ws_msg_timestamps: list[float] = []

    try:
        while True:
            # Receive message
            data = await websocket.receive_text()

            # --- WebSocket rate limiting ---
            _now = time.time()
            _ws_msg_timestamps[:] = [t for t in _ws_msg_timestamps if _now - t < 60]
            if len(_ws_msg_timestamps) >= MAX_WS_MESSAGES_PER_MINUTE:
                await manager.send_error(session_id, "Rate limit exceeded. Please slow down.")
                continue
            _ws_msg_timestamps.append(_now)

            try:
                message_data = json.loads(data)
            except json.JSONDecodeError:
                await manager.send_error(session_id, "Invalid JSON message")
                continue

            msg_type = message_data.get("type", "chat")

            if msg_type == "ping":
                # Respond to ping
                await manager.send_to_session(session_id, {"type": "pong"})
                continue

            elif msg_type == "chat":
                # Handle chat message
                content = message_data.get("data", {}).get("content", "")
                raw_images = message_data.get("data", {}).get("images", [])
                brand_slug = message_data.get("data", {}).get("brand")

                # Validate and cap incoming images
                images: list[str] = []
                for img in raw_images[:MAX_IMAGES_PER_MESSAGE]:
                    if not isinstance(img, str):
                        continue
                    if len(img) > MAX_IMAGE_SIZE_B64:
                        logger.warning("Oversized image rejected for session %s", session_id)
                        continue
                    images.append(img)
                workflow_mode = message_data.get("data", {}).get("mode", "plan")  # Default to plan

                if brand_slug:
                    session_brands[session_id] = brand_slug

                if not content and not images:
                    await manager.send_error(session_id, "Empty message")
                    continue
                if not content and images:
                    content = "Mirá las imágenes adjuntas y ayudame con un plan de contenido basado en ellas."

                # Store user message
                user_message = ChatMessage(
                    role="user",
                    content=content,
                    images=images,
                    timestamp=datetime.now(),
                )
                conversations[session_id].append(user_message)
                _trim_conversation(session_id)

                # Keep latest non-confirmation request as candidate for orchestrator build
                if content and not _is_build_confirmation(content):
                    pending_build_requests[session_id] = content

                # If user confirms build, execute real orchestrator with pending request
                active_brand = brand_slug or session_brands.get(session_id)
                if _is_build_confirmation(content):
                    pending_request = pending_build_requests.get(session_id)
                    if not active_brand:
                        await manager.send_error(
                            session_id,
                            "Para ejecutar build necesitás seleccionar una marca.",
                        )
                        continue
                    if not pending_request:
                        await manager.send_error(
                            session_id,
                            "No hay pedido pendiente para ejecutar. Enviá primero un pedido de campaña.",
                        )
                        continue

                    asyncio.create_task(
                        _run_orchestrator_build(session_id, active_brand, pending_request)
                    )
                    continue

                # Load brand
                brand = _load_brand(brand_slug)

                # Build context from conversation history
                context = [
                    {"role": msg.role, "content": msg.content}
                    for msg in conversations[session_id][:-1]  # Exclude current message
                ]

                # Process with StrategistAgent (include images as reference and workflow mode)
                try:
                    # Pass workflow mode and brand_slug (para pipeline)
                    response_content, plan = strategist.chat(
                        message=content,
                        brand=brand,
                        context=context if context else None,
                        images=images if images else None,
                        workflow_mode=workflow_mode,
                        brand_slug=brand_slug,
                    )
                except Exception as e:
                    logger.error(f"StrategistAgent error: {e}")
                    response_content = f"Error al procesar tu mensaje: {e}"
                    plan = None

                # Save plan if created
                plan_dict = None
                should_auto_generate = False
                if plan:
                    # Save plan to file
                    plan_file = get_plans_dir() / f"{plan.id}.json"
                    plan.save(plan_file)
                    logger.info(f"Plan saved: {plan.id}")

                    # Check if user wants to generate (approve and execute)
                    should_auto_generate = strategist._should_generate_content(content)

                    # Convert plan to dict for WebSocket
                    plan_response = _plan_to_response(plan)
                    plan_dict = plan_response.model_dump(mode="json")

                # Send response
                await manager.send_chat_message(
                    session_id,
                    role="assistant",
                    content=response_content,
                    plan=plan_dict,
                )

                # Store assistant message
                assistant_message = ChatMessage(
                    role="assistant",
                    content=response_content,
                    timestamp=datetime.now(),
                )
                conversations[session_id].append(assistant_message)
                _trim_conversation(session_id)

                # Auto-generate if user requested it (auto-approve mode)
                if plan and should_auto_generate:
                    if active_brand := (brand_slug or session_brands.get(session_id)):
                        logger.info("Auto-triggering real orchestrator build from chat intent")
                        asyncio.create_task(
                            _run_orchestrator_build(session_id, active_brand, content)
                        )
                    else:
                        await manager.send_error(
                            session_id,
                            "Detecté intención de build pero falta marca seleccionada.",
                        )

            elif msg_type == "build_orchestrator":
                data = message_data.get("data", {})
                brand_slug = data.get("brand") or session_brands.get(session_id)
                user_request = data.get("request") or pending_build_requests.get(session_id)

                if not brand_slug:
                    await manager.send_error(
                        session_id, "Para build_orchestrator se requiere brand"
                    )
                    continue
                if not user_request:
                    await manager.send_error(
                        session_id,
                        "No hay pedido para ejecutar. Enviá un mensaje de campaña primero.",
                    )
                    continue

                asyncio.create_task(_run_orchestrator_build(session_id, brand_slug, user_request))
                continue

            elif msg_type == "approve_plan":
                # Handle plan approval with validation and transition to BUILD mode
                plan_id = message_data.get("data", {}).get("plan_id")
                item_ids = message_data.get("data", {}).get("item_ids", [])
                auto_approve = message_data.get("data", {}).get("auto_approve", False)

                if not plan_id:
                    await manager.send_error(session_id, "plan_id is required")
                    continue

                try:
                    # Approve and validate plan
                    plan, validation = plan_manager.approve_plan(
                        plan_id=plan_id,
                        item_ids=item_ids if item_ids else None,
                        auto_approve=auto_approve,
                    )

                    # Send validation results
                    await manager.send_to_session(
                        session_id,
                        {
                            "type": "plan_approved",
                            "data": {
                                "plan_id": plan_id,
                                "approved_items": item_ids or "all",
                                "validation": validation,
                                "ready_for_build": validation["valid"],
                            },
                        },
                    )

                    # If validation failed, send errors but don't block
                    if not validation["valid"]:
                        await manager.send_to_session(
                            session_id,
                            {
                                "type": "validation_warning",
                                "data": {
                                    "plan_id": plan_id,
                                    "errors": validation["errors"],
                                    "warnings": validation["warnings"],
                                    "message": "Plan aprobado pero tiene errores. La generación puede fallar.",
                                },
                            },
                        )

                    # Only proceed to build if validation passed or auto_approve
                    if validation["valid"] or auto_approve:
                        # Transition to BUILD mode - start generation
                        import asyncio

                        from ..routes.generate import execute_generation

                        await manager.send_to_session(
                            session_id,
                            {
                                "type": "mode_changed",
                                "data": {
                                    "mode": "build",
                                    "plan_id": plan_id,
                                    "message": "Modo BUILD activado - Iniciando generación...",
                                },
                            },
                        )

                        # Run generation in background
                        asyncio.create_task(
                            execute_generation(
                                plan_id=plan_id,
                                item_ids=item_ids if item_ids else None,
                                session_id=session_id,
                            )
                        )
                    else:
                        # Validation failed - don't proceed to build
                        await manager.send_to_session(
                            session_id,
                            {
                                "type": "build_blocked",
                                "data": {
                                    "plan_id": plan_id,
                                    "message": "No se puede iniciar BUILD mode. Corregí los errores primero.",
                                    "errors": validation["errors"],
                                },
                            },
                        )

                except PlanValidationError as e:
                    logger.error(f"Plan validation failed: {e}")
                    await manager.send_error(session_id, f"Validación falló: {e}")
                except Exception as e:
                    logger.error(f"Plan approval failed: {e}", exc_info=True)
                    await manager.send_error(session_id, f"Error al aprobar plan: {e}")

            else:
                await manager.send_error(session_id, f"Unknown message type: {msg_type}")

    except WebSocketDisconnect:
        await manager.disconnect(websocket, session_id)
        logger.info(f"Client disconnected: {session_id}")


@router.get("/chat/history/{session_id}")
async def get_chat_history(session_id: str):
    """Get chat history for a session."""
    messages = conversations.get(session_id, [])
    return {
        "session_id": session_id,
        "messages": [msg.model_dump() for msg in messages],
        "count": len(messages),
    }


@router.delete("/chat/history/{session_id}")
async def clear_chat_history(session_id: str):
    """Clear chat history for a session."""
    if session_id in conversations:
        del conversations[session_id]
    return {"status": "cleared", "session_id": session_id}
