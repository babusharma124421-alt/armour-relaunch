interface QuizQuestionProps {
  question: string
  options: string[]
  correctIndex: number
  selectedIndex: number | null
  answered: boolean
  onSelect: (index: number) => void
}

export function QuizQuestion({ question, options, correctIndex, selectedIndex, answered, onSelect }: QuizQuestionProps) {
  return (
    <div className="glass-panel rounded-3xl p-5 sm:p-8">
      <h2 className="text-xl font-semibold leading-8 text-white sm:text-2xl">{question}</h2>
      <div className="mt-7 grid gap-3">
        {options.map((option, index) => {
          const isCorrect = index === correctIndex
          const isSelected = index === selectedIndex
          let state = 'border-slate-700 bg-slate-900/60 text-slate-200 hover:border-sky-400/60 hover:bg-slate-800'
          if (answered && isCorrect) state = 'border-risk-safe/70 bg-risk-safe/10 text-green-100'
          if (answered && isSelected && !isCorrect) state = 'border-risk-critical/70 bg-risk-critical/10 text-red-100'
          return (
            <button key={option} type="button" disabled={answered} onClick={() => onSelect(index)} className={`flex items-start gap-4 rounded-2xl border p-4 text-left transition disabled:cursor-default ${state}`}>
              <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-white/5 text-sm font-bold text-slate-400">{String.fromCharCode(65 + index)}</span>
              <span className="pt-0.5 leading-6">{option}</span>
            </button>
          )
        })}
      </div>
    </div>
  )
}
