import { CheckCircle2, RotateCcw, Share2, Trophy } from 'lucide-react'
import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { QuizQuestion } from '../components/QuizQuestion'
import quizEn from '../content/quiz_en.json'
import quizHi from '../content/quiz_hi.json'

interface QuizItem {
  id: string
  question: string
  options: string[]
  correct_index: number
  explanation: string
}

export function Quiz() {
  const { t, i18n } = useTranslation()
  const questions = useMemo(() => (i18n.language.toLowerCase().startsWith('hi') ? quizHi : quizEn) as QuizItem[], [i18n.language])
  const [current, setCurrent] = useState(0)
  const [selected, setSelected] = useState<number | null>(null)
  const [score, setScore] = useState(0)
  const [finished, setFinished] = useState(false)
  const question = questions[current]

  const selectAnswer = (index: number) => {
    if (selected !== null) return
    setSelected(index)
    if (index === question.correct_index) setScore((value) => value + 1)
  }

  const next = () => {
    if (current === questions.length - 1) setFinished(true)
    else {
      setCurrent((value) => value + 1)
      setSelected(null)
    }
  }

  const reset = () => {
    setCurrent(0)
    setSelected(null)
    setScore(0)
    setFinished(false)
  }

  const shareScore = async () => {
    const text = t('quiz.share_text', { score, total: questions.length })
    try {
      if (navigator.share) await navigator.share({ text })
      else {
        await navigator.clipboard.writeText(text)
        window.alert(t('action.copied'))
      }
    } catch {
      // Share cancellation is a normal user action and needs no error UI.
    }
  }

  return (
    <div className="page-shell">
      <div className="mb-7"><p className="eyebrow">Learn by doing</p><h1 className="mt-2 text-3xl font-bold tracking-tight text-white sm:text-4xl">{t('quiz.title')}</h1><p className="mt-2 text-sm leading-6 text-slate-400">{t('quiz.subtitle')}</p></div>
      {finished ? <div className="glass-panel mx-auto max-w-2xl rounded-3xl p-7 text-center sm:p-10"><div className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl bg-yellow-400/10 text-yellow-300"><Trophy className="h-8 w-8" /></div><p className="eyebrow mt-6">{t('quiz.score')}</p><p className="mt-2 text-6xl font-bold text-white">{score}<span className="text-2xl text-slate-500">/{questions.length}</span></p><p className="mx-auto mt-4 max-w-md text-sm leading-6 text-slate-400">{t('quiz.summary', { score, total: questions.length })}</p><div className="mt-7 flex flex-wrap justify-center gap-3"><button type="button" onClick={() => void shareScore()} className="secondary-button"><Share2 className="h-4 w-4" />{t('quiz.share')}</button><button type="button" onClick={reset} className="secondary-button"><RotateCcw className="h-4 w-4" />{t('practice.restart')}</button></div><div className="mt-8 grid gap-3 sm:grid-cols-2"><Link to="/learn" className="primary-button"><CheckCircle2 className="h-4 w-4" />{t('quiz.read_learn')}</Link><Link to="/practice" className="secondary-button">{t('quiz.try_practice')}</Link></div></div> : <div className="mx-auto max-w-3xl"><div className="mb-4 flex items-center justify-between gap-4 text-sm text-slate-500"><span>{t('quiz.question', { current: current + 1, total: questions.length })}</span><span>{score} {t('quiz.score').toLowerCase()}</span></div><QuizQuestion question={question.question} options={question.options} correctIndex={question.correct_index} selectedIndex={selected} answered={selected !== null} onSelect={selectAnswer} />{selected !== null && <div className={`mt-4 rounded-2xl border p-5 ${selected === question.correct_index ? 'border-risk-safe/30 bg-risk-safe/5' : 'border-risk-suspicious/30 bg-risk-suspicious/5'}`}><p className={`text-sm font-bold ${selected === question.correct_index ? 'text-risk-safe' : 'text-risk-suspicious'}`}>{selected === question.correct_index ? t('quiz.correct') : t('quiz.incorrect')}</p><p className="mt-2 text-xs font-semibold uppercase tracking-wider text-slate-500">{t('quiz.explanation')}</p><p className="mt-2 text-sm leading-6 text-slate-300">{question.explanation}</p><button type="button" onClick={next} className="primary-button mt-5">{current === questions.length - 1 ? t('quiz.finish') : t('action.next')}</button></div>}</div>}
    </div>
  )
}
