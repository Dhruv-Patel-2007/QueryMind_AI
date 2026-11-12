import { Database, Sparkles, Terminal, Activity } from 'lucide-react';

export default function App() {
  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans">
      {/* Top Header */}
      <header className="border-b border-slate-800 bg-slate-900/60 backdrop-blur px-6 py-4 flex items-center justify-between sticky top-0 z-50">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-xl bg-indigo-500/10 border border-indigo-500/20 text-indigo-400">
            <Sparkles className="w-5 h-5" />
          </div>
          <div>
            <h1 className="text-lg font-bold bg-gradient-to-r from-white via-slate-200 to-indigo-300 bg-clip-text text-transparent">
              QueryMind AI 2.0
            </h1>
            <p className="text-xs text-slate-400">Conversational Text-to-SQL & Academic Data Intelligence</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span className="flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            <Activity className="w-3.5 h-3.5" />
            Deterministic Local Engine
          </span>
        </div>
      </header>

      {/* Main Container */}
      <main className="flex-1 max-w-7xl w-full mx-auto p-6 flex flex-col gap-6">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="p-5 rounded-2xl bg-slate-900/80 border border-slate-800 flex items-start gap-4">
            <div className="p-2.5 rounded-xl bg-indigo-500/10 border border-indigo-500/20 text-indigo-400">
              <Database className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-semibold text-slate-200">Academic Domain</h3>
              <p className="text-xs text-slate-400 mt-1">9 Relational Tables: Students, Courses, Enrollments, Assessments & Marks</p>
            </div>
          </div>
          <div className="p-5 rounded-2xl bg-slate-900/80 border border-slate-800 flex items-start gap-4">
            <div className="p-2.5 rounded-xl bg-violet-500/10 border border-violet-500/20 text-violet-400">
              <Sparkles className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-semibold text-slate-200">NLP & Intent Engine</h3>
              <p className="text-xs text-slate-400 mt-1">NLTK Tokenizer, POS Tagger & Calibrated Multinomial Logistic Intent Model</p>
            </div>
          </div>
          <div className="p-5 rounded-2xl bg-slate-900/80 border border-slate-800 flex items-start gap-4">
            <div className="p-2.5 rounded-xl bg-sky-500/10 border border-sky-500/20 text-sky-400">
              <Terminal className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-semibold text-slate-200">SQLGlot Guardrails</h3>
              <p className="text-xs text-slate-400 mt-1">AST Analysis, Read-Only Enforcement, and QueryDoctor Self-Diagnosis</p>
            </div>
          </div>
        </div>

        {/* Center Welcome Card */}
        <div className="p-8 rounded-2xl bg-gradient-to-b from-slate-900 to-slate-950 border border-slate-800 text-center flex flex-col items-center justify-center py-16">
          <div className="w-16 h-16 rounded-2xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400 mb-4 shadow-lg shadow-indigo-500/5">
            <Sparkles className="w-8 h-8" />
          </div>
          <h2 className="text-2xl font-bold text-slate-100">Welcome to QueryMind AI 2.0</h2>
          <p className="text-sm text-slate-400 max-w-lg mt-2 leading-relaxed">
            Phase 1 Scaffolding is active. The conversational natural language query pipeline,
            interactive Recharts dashboard, and TrustLens transparency inspector are ready to be integrated.
          </p>
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-800/80 py-4 px-6 text-center text-xs text-slate-500">
        QueryMind AI 2.0 — Final Year Capstone Project — Academic Institution Text-to-SQL System
      </footer>
    </div>
  );
}
