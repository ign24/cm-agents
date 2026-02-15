"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  MessageSquare,
  Palette,
  Calendar,
  FileText,
  Image,
  BarChart3,
} from "lucide-react";
import { useChatStore } from "@/stores/chatStore";
import { api, type Brand } from "@/lib/api";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarRail,
  SidebarSeparator,
  useSidebar,
} from "@/components/ui/sidebar";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { cn } from "@/lib/utils";

const navItems = [
  { title: "Chat", href: "/", icon: MessageSquare },
  { title: "Marcas", href: "/brands", icon: Palette },
  { title: "Campañas", href: "/campaigns", icon: Calendar },
] as const;

const quickActions = [
  { title: "Ver planes", href: "/plans", icon: FileText },
  { title: "Galería", href: "/gallery", icon: Image },
  { title: "Calendario", href: "/calendar", icon: BarChart3 },
] as const;

const BRAND_NONE = "__none__";

export function AppSidebar() {
  const pathname = usePathname();
  const { setOpenMobile, isMobile } = useSidebar();
  const { selectedBrand, setSelectedBrand } = useChatStore();
  const [brands, setBrands] = useState<Brand[]>([]);
  const [brandsLoading, setBrandsLoading] = useState(true);

  useEffect(() => {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 10000);
    api
      .getBrands({ signal: controller.signal })
      .then((res) => setBrands(res.brands ?? []))
      .catch(() => setBrands([]))
      .finally(() => {
        clearTimeout(timeoutId);
        setBrandsLoading(false);
      });
  }, []);

  useEffect(() => {
    if (isMobile) setOpenMobile(false);
  }, [pathname, isMobile, setOpenMobile]);

  return (
    <Sidebar collapsible="icon" className="border-r border-sidebar-border">
      <SidebarHeader className="border-b border-sidebar-border">
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton
              asChild
              size="lg"
              tooltip="CM Agents"
              className="data-[state=open]:bg-sidebar-accent"
            >
              <Link href="/">
                <Palette className="text-sidebar-primary" />
                <span className="font-semibold">CM Agents</span>
              </Link>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>

      <SidebarContent className="gap-0">
        <SidebarGroup>
          <SidebarGroupLabel>Navegación</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {navItems.map((item) => {
                const isActive =
                  item.href === "/"
                    ? pathname === "/"
                    : pathname.startsWith(item.href);
                return (
                  <SidebarMenuItem key={item.href}>
                    <SidebarMenuButton
                      asChild
                      isActive={isActive}
                      tooltip={item.title}
                    >
                      <Link href={item.href}>
                        <item.icon />
                        <span>{item.title}</span>
                      </Link>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                );
              })}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>

        <SidebarSeparator />

        <SidebarGroup className="group-data-[collapsible=icon]:hidden">
          <SidebarGroupLabel>Marca activa</SidebarGroupLabel>
          <SidebarGroupContent>
            {brandsLoading ? (
              <div className="h-9 rounded-md bg-sidebar-accent/50 animate-pulse px-2 flex items-center">
                <span className="text-xs text-sidebar-foreground/60">
                  Cargando…
                </span>
              </div>
            ) : (
              <Select
                value={selectedBrand ?? BRAND_NONE}
                onValueChange={(v) =>
                  setSelectedBrand(v === BRAND_NONE ? null : v)
                }
              >
                <SelectTrigger
                  className="h-9 w-full bg-background/80 border-sidebar-border text-sm"
                  data-sidebar="input"
                >
                  <SelectValue placeholder="Sin marca seleccionada" />
                </SelectTrigger>
                <SelectContent side="right" align="start">
                  <SelectItem value={BRAND_NONE}>
                    <span className="text-muted-foreground">
                      Sin marca seleccionada
                    </span>
                  </SelectItem>
                  {brands.map((b) => (
                    <SelectItem key={b.slug} value={b.slug}>
                      {b.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
          </SidebarGroupContent>
        </SidebarGroup>

        <SidebarSeparator />

        <SidebarGroup>
          <SidebarGroupLabel>Acciones rápidas</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {quickActions.map((item) => {
                const isActive = pathname.startsWith(item.href);
                return (
                  <SidebarMenuItem key={item.href}>
                    <SidebarMenuButton
                      asChild
                      isActive={isActive}
                      tooltip={item.title}
                    >
                      <Link href={item.href}>
                        <item.icon />
                        <span>{item.title}</span>
                      </Link>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                );
              })}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>

      <SidebarFooter className="border-t border-sidebar-border">
        <div
          className={cn(
            "flex items-center gap-2 px-2 py-1.5 text-xs text-sidebar-foreground/70",
            "group-data-[collapsible=icon]:hidden"
          )}
        >
          <kbd className="rounded bg-sidebar-accent px-1.5 py-0.5 font-mono text-[10px]">
            ⌘B
          </kbd>
          <span>Alternar panel</span>
        </div>
      </SidebarFooter>

      {!isMobile && <SidebarRail />}
    </Sidebar>
  );
}
