import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import AskAnything from '../components/AskAnything'
import PromptTable from '../components/PromptTable'
import SuggestedPrompts from '../components/SuggestedPrompts'
import { ErrorRetry } from '../components/PageState'

export default function PromptBankPage() {
  const prompts = useQuery({ queryKey: ['prompts'], queryFn: api.prompts })

  return (
    <div className="space-y-6 animate-fade-in">
      <div>
        <p className="text-xs font-semibold uppercase tracking-wider text-lce-orange-dark mb-1">Measure</p>
        <h2 className="text-2xl font-semibold">Prompt Bank</h2>
        <p className="text-text-secondary">Ask anything, see every tracked prompt, and track the ones that matter.</p>
      </div>

      <AskAnything />

      {prompts.isError ? (
        <ErrorRetry message="Couldn't load the tracked prompts." onRetry={() => prompts.refetch()} />
      ) : prompts.data ? (
        <PromptTable rows={prompts.data} />
      ) : (
        <div className="card p-6 h-64 bg-gray-100 animate-pulse" />
      )}

      <SuggestedPrompts />
    </div>
  )
}
