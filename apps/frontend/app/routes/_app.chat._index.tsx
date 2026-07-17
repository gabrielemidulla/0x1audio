import { useState } from "react"
import { useNavigate, useOutletContext } from "react-router"

import { ChatPrompter } from "~/components/chat-prompter"
import { GreetingStage } from "~/components/greeting-hero"
import { api } from "~/lib/api"
import type { AppOutletContext } from "~/routes/_app"

export default function ChatIndexPage() {
  const { user } = useOutletContext<AppOutletContext>()
  const navigate = useNavigate()
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  return (
    <div className="flex min-h-0 flex-1 flex-col items-center justify-center pb-16 text-center">
      <GreetingStage email={user.email}>
        <ChatPrompter
          className="w-full"
          autoFocus
          disabled={busy}
          onSubmit={async (message) => {
            setBusy(true)
            setError(null)
            const { data, error: apiError } = await api.v1.createChat({
              body: { message },
            })
            setBusy(false)
            if (apiError || !data) {
              setError("Could not start chat")
              return
            }
            void navigate(`/chat/${data.id}`, { state: { seed: data } })
          }}
        />
      </GreetingStage>
      {error ? <p className="text-destructive mt-4 text-sm">{error}</p> : null}
    </div>
  )
}
