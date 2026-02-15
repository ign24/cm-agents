import { ChatWindow } from "@/components/chat";

export default function Home() {
  return (
    <div className="container mx-auto flex flex-1 flex-col gap-6 p-4 md:p-6">
      <div className="flex min-h-[400px] flex-1 flex-col">
        <ChatWindow />
      </div>
    </div>
  );
}
