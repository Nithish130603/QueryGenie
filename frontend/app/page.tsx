"use client";

import { useState, useRef, useEffect } from "react";
import axios from "axios";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface QueryResult {
  question: string;
  success: boolean;
  sql: string | null;
  data: Record<string, any>[] | null;
  columns: string[];
  row_count: number;
  error: string | null;
  explanation: string | null;
}

/* ───────────────────────── SVG Icons ───────────────────────── */
const SendIcon = () => (
  <svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M5 12h14M12 5l7 7-7 7" />
  </svg>
);
const SparkleIcon = () => (
  <svg width="14" height="14" fill="currentColor" viewBox="0 0 24 24">
    <path d="M12 2L9.19 8.63 2 9.24l5.46 4.73L5.82 21 12 17.27 18.18 21l-1.64-7.03L22 9.24l-7.19-.61L12 2z" />
  </svg>
);
const TrashIcon = () => (
  <svg width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
  </svg>
);
const DatabaseIcon = () => (
  <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
    <ellipse cx="12" cy="5" rx="9" ry="3" />
    <path d="M3 5v6c0 1.657 4.03 3 9 3s9-1.343 9-3V5" />
    <path d="M3 11v6c0 1.657 4.03 3 9 3s9-1.343 9-3v-6" />
  </svg>
);
const UploadIcon = () => (
  <svg width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
  </svg>
);
const SchemaIcon = () => (
  <svg width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 6A2.25 2.25 0 016 3.75h2.25A2.25 2.25 0 0110.5 6v2.25a2.25 2.25 0 01-2.25 2.25H6a2.25 2.25 0 01-2.25-2.25V6zM3.75 15.75A2.25 2.25 0 016 13.5h2.25a2.25 2.25 0 012.25 2.25V18a2.25 2.25 0 01-2.25 2.25H6A2.25 2.25 0 013.75 18v-2.25zM13.5 6a2.25 2.25 0 012.25-2.25H18A2.25 2.25 0 0120.25 6v2.25A2.25 2.25 0 0118 10.5h-2.25a2.25 2.25 0 01-2.25-2.25V6zM13.5 15.75a2.25 2.25 0 012.25-2.25H18a2.25 2.25 0 012.25 2.25V18A2.25 2.25 0 0118 20.25h-2.25a2.25 2.25 0 01-2.25-2.25v-2.25z" />
  </svg>
);
const ChevronIcon = ({ open }: { open: boolean }) => (
  <svg
    width="12" height="12" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}
    className={`transition-transform duration-200 ${open ? "rotate-90" : ""}`}
  >
    <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
  </svg>
);
const CheckIcon = () => (
  <svg width="12" height="12" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
  </svg>
);
const DownloadIcon = () => (
  <svg width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" />
  </svg>
);

/* ───────────── parse explanation into structured parts ───────────── */
function parseExplanation(text: string) {
  // Split on common patterns: "* ", "- ", numbered "1. ", "1) "
  const lines = text.split(/(?:\n|(?<=\.)\s*)(?=[\*\-•]\s|(?:\d+[\.\)]\s))/g).filter(Boolean);

  if (lines.length <= 1) {
    // Try splitting on ". " followed by a keyword
    const parts = text.split(/(?<=\.)\s+(?=(?:The |This |It |Each |Finally ))/g);
    if (parts.length > 1) return parts.map((p) => p.trim()).filter(Boolean);
    return [text];
  }

  return lines.map((line) => line.replace(/^[\*\-•]\s*/, "").replace(/^\d+[\.\)]\s*/, "").trim()).filter(Boolean);
}

/* ───────────────────────── main component ───────────────────────── */
export default function Home() {
  const [question, setQuestion] = useState("");
  const [history, setHistory] = useState<QueryResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [explaining, setExplaining] = useState<number | null>(null);
  const [models, setModels] = useState<Record<string, string>>({});
  const [selectedModel, setSelectedModel] = useState("groq-llama3");
  const [examples, setExamples] = useState<{ question: string; category: string }[]>([]);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [schemaText, setSchemaText] = useState("");
  const [schemaOpen, setSchemaOpen] = useState(false);
  const [dbName, setDbName] = useState("Chinook Music Store");
  const [uploading, setUploading] = useState(false);
  const [copied, setCopied] = useState<number | null>(null);
  const chatEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const refreshData = () => {
    axios.get(`${API_URL}/models`).then((res) => setModels(res.data)).catch(() => { });
    axios.get(`${API_URL}/examples`).then((res) => setExamples(res.data.examples)).catch(() => { });
    axios.get(`${API_URL}/schema`).then((res) => {
      setSchemaText(res.data.schema);
      setDbName(res.data.db_name);
    }).catch(() => { });
  };

  useEffect(() => { refreshData(); }, []);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [history, loading]);

  const askQuestion = async (q: string) => {
    if (!q.trim() || loading) return;
    const trimmed = q.trim();
    setLoading(true);
    setQuestion("");
    inputRef.current?.focus();

    try {
      const res = await axios.post(`${API_URL}/query`, { question: trimmed, model_key: selectedModel });
      setHistory((prev) => [...prev, { question: trimmed, ...res.data, explanation: null }]);
    } catch (err: any) {
      setHistory((prev) => [
        ...prev,
        { question: trimmed, success: false, sql: null, data: null, columns: [], row_count: 0, error: err.message || "Something went wrong", explanation: null },
      ]);
    }
    setLoading(false);
  };

  const explainQuery = async (index: number) => {
    const entry = history[index];
    if (!entry.sql) return;
    setExplaining(index);
    try {
      const res = await axios.post(`${API_URL}/explain`, { sql: entry.sql, model_key: selectedModel });
      setHistory((prev) => prev.map((item, i) => (i === index ? { ...item, explanation: res.data.explanation } : item)));
    } catch (err) { console.error(err); }
    setExplaining(null);
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    const formData = new FormData();
    formData.append("file", file);
    try {
      await axios.post(`${API_URL}/upload`, formData, { headers: { "Content-Type": "multipart/form-data" } });
      setHistory([]);
      refreshData();
    } catch (err) { console.error(err); }
    setUploading(false);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const resetToDemo = async () => {
    try {
      await axios.post(`${API_URL}/reset`);
      setHistory([]);
      refreshData();
    } catch (err) { console.error(err); }
  };

  const copySQL = (sql: string, index: number) => {
    navigator.clipboard.writeText(sql);
    setCopied(index);
    setTimeout(() => setCopied(null), 2000);
  };

  const formatNumber = (val: any) => {
    if (typeof val === "number") {
      return Number.isInteger(val) ? val.toLocaleString() : val.toLocaleString(undefined, { maximumFractionDigits: 2 });
    }
    return val?.toString() || "—";
  };

  const downloadHistory = () => {
    const rows = [["question", "sql", "success", "rows", "model"]];
    history.forEach((entry) => {
      rows.push([
        entry.question,
        entry.sql || "",
        entry.success ? "true" : "false",
        entry.row_count.toString(),
        selectedModel,
      ]);
    });
    const csv = rows.map((r) => r.map((c) => `"${c.replace(/"/g, '""')}"`).join(",")).join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "querygenie_history.csv";
    a.click();
    URL.revokeObjectURL(url);
  };

  const isSingleMetric = (entry: QueryResult) =>
    entry.success && entry.data && entry.data.length === 1 && entry.columns.length <= 3;

  /* ─── Parse schema into tables for display ─── */
  const schemaTables = schemaText
    ? schemaText.split(/(?=Table: )/).filter((s) => s.trim().startsWith("Table:")).map((block) => {
      const name = block.match(/Table: (\w+)/)?.[1] || "";
      return { name, block: block.trim() };
    })
    : [];

  return (
    <div className="h-screen flex overflow-hidden" style={{ background: "linear-gradient(145deg, #0a0e1a 0%, #0d1321 50%, #0a0e1a 100%)" }}>

      {/* ═══════════ SIDEBAR ═══════════ */}
      <aside className={`${sidebarOpen ? "w-[280px]" : "w-0"} shrink-0 transition-all duration-300 overflow-hidden`}>
        <div className="w-[280px] h-full flex flex-col border-r border-white/5" style={{ background: "linear-gradient(180deg, rgba(15,20,35,0.95) 0%, rgba(10,14,26,0.98) 100%)" }}>

          {/* Logo */}
          <div className="px-5 pt-5 pb-3">
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-lg flex items-center justify-center text-lg" style={{ background: "linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%)" }}>🧞</div>
              <div>
                <h1 className="text-[15px] font-semibold text-white tracking-tight">QueryGenie</h1>
                <p className="text-[10px] text-white/30 tracking-wide uppercase">Natural Language → SQL</p>
              </div>
            </div>
          </div>

          <div className="w-full h-px bg-gradient-to-r from-transparent via-white/8 to-transparent" />

          <div className="flex-1 overflow-y-auto px-4 py-4 space-y-5 scrollbar-thin">

            {/* Model */}
            <div>
              <label className="text-[10px] font-medium text-white/50 uppercase tracking-widest mb-2 block">Model</label>
              <div className="relative">
                <select
                  value={selectedModel}
                  onChange={(e) => setSelectedModel(e.target.value)}
                  className="w-full appearance-none bg-white/[0.04] border border-white/[0.06] rounded-lg px-3 py-2 text-[13px] text-white/80 focus:outline-none focus:border-indigo-500/40 transition cursor-pointer hover:bg-white/[0.06]"
                >
                  {Object.entries(models).map(([key]) => (
                    <option key={key} value={key} className="bg-gray-900">{key}</option>
                  ))}
                </select>
                <div className="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none text-white/20">
                  <svg width="12" height="12" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
                  </svg>
                </div>
              </div>
            </div>

            {/* Database */}
            <div>
              <label className="text-[10px] font-medium text-white/50 uppercase tracking-widest mb-2 flex items-center gap-1.5">
                <DatabaseIcon /> Database
              </label>
              <div className="bg-white/[0.02] border border-white/[0.06] rounded-lg px-3 py-2.5 mb-2">
                <p className="text-[12px] text-white/80">{dbName === "chinook_demo" ? "Chinook Music Store" : dbName}</p>
                <p className="text-[10px] text-white/40 mt-0.5">{schemaTables.length} tables · SQLite</p>
              </div>
              <div className="flex gap-1.5">
                <button
                  onClick={() => fileInputRef.current?.click()}
                  disabled={uploading}
                  className="flex-1 flex items-center justify-center gap-1.5 text-[11px] text-white/60 hover:text-white/90 bg-white/[0.03] hover:bg-white/[0.06] border border-white/[0.06] rounded-lg py-1.5 transition"
                >
                  <UploadIcon />
                  {uploading ? "Uploading..." : "Upload"}
                </button>
                <button
                  onClick={resetToDemo}
                  className="flex-1 flex items-center justify-center gap-1.5 text-[11px] text-white/60 hover:text-white/90 bg-white/[0.03] hover:bg-white/[0.06] border border-white/[0.06] rounded-lg py-1.5 transition"
                >
                  Demo DB
                </button>
              </div>
              <input
                ref={fileInputRef}
                type="file"
                accept=".sqlite,.db,.csv"
                onChange={handleFileUpload}
                className="hidden"
              />
            </div>

            {/* Schema Viewer */}
            <div>
              <button
                onClick={() => setSchemaOpen(!schemaOpen)}
                className="w-full flex items-center gap-1.5 text-[10px] font-medium text-white/50 uppercase tracking-widest mb-2 hover:text-white/50 transition"
              >
                <ChevronIcon open={schemaOpen} />
                <SchemaIcon /> Schema
              </button>
              {schemaOpen && (
                <div className="space-y-1 animate-slideDown">
                  {schemaTables.map((t) => (
                    <SchemaTable key={t.name} name={t.name} block={t.block} />
                  ))}
                </div>
              )}
            </div>

            {/* Examples */}
            <div>
              <label className="text-[10px] font-medium text-white/50 uppercase tracking-widest mb-2 flex items-center gap-1.5">
                <SparkleIcon /> Examples
              </label>
              <div className="space-y-1">
                {examples.map((ex, i) => (
                  <button
                    key={i}
                    onClick={() => askQuestion(ex.question)}
                    disabled={loading}
                    className="w-full text-left text-[12px] leading-relaxed text-white/70 hover:text-white/95 bg-white/[0.02] hover:bg-white/[0.06] rounded-lg px-3 py-2 transition-all duration-200 border border-transparent hover:border-white/[0.06] disabled:opacity-40"
                  >
                    {ex.question}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Bottom */}
          {history.length > 0 && (
            <div className="px-4 pb-4">
              <div className="w-full h-px bg-gradient-to-r from-transparent via-white/8 to-transparent mb-3" />
              <div className="flex items-center gap-3">
                <button onClick={() => setHistory([])} className="flex items-center gap-2 text-[11px] text-white/40 hover:text-red-400/80 transition-colors duration-200">
                  <TrashIcon /> Clear
                </button>
                <button onClick={downloadHistory} className="flex items-center gap-2 text-[11px] text-white/40 hover:text-indigo-400/80 transition-colors duration-200">
                  <DownloadIcon /> Export CSV
                </button>
              </div>
            </div>
          )}
        </div>
      </aside>

      {/* ═══════════ MAIN ═══════════ */}
      <main className="flex-1 flex flex-col min-w-0">

        {/* Top Bar */}
        <div className="h-12 shrink-0 flex items-center px-4 border-b border-white/5">
          <button onClick={() => setSidebarOpen(!sidebarOpen)} className="w-8 h-8 flex items-center justify-center rounded-lg hover:bg-white/5 text-white/40 hover:text-white/70 transition">
            <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25h16.5" />
            </svg>
          </button>
          <div className="ml-3 text-[12px] text-white/20">
            {selectedModel && <span className="bg-white/[0.04] px-2 py-0.5 rounded-full">{selectedModel}</span>}
          </div>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto">
          <div className="max-w-3xl mx-auto px-4 py-8 space-y-6">

            {/* Empty State */}
            {history.length === 0 && !loading && (
              <div className="flex flex-col items-center justify-center pt-24 animate-fadeIn">
                <div className="w-16 h-16 rounded-2xl flex items-center justify-center text-3xl mb-5" style={{ background: "linear-gradient(135deg, rgba(99,102,241,0.15) 0%, rgba(139,92,246,0.1) 100%)", border: "1px solid rgba(99,102,241,0.1)" }}>🧞</div>
                <h2 className="text-[18px] font-medium text-white/70 mb-2">What would you like to know?</h2>
                <p className="text-[13px] text-white/40 max-w-sm text-center leading-relaxed">
                  Ask questions about your database in plain English. I&apos;ll write the SQL and show you the results.
                </p>
              </div>
            )}

            {/* Chat History */}
            {history.map((entry, i) => (
              <div key={i} className="space-y-3 animate-slideUp">

                {/* User bubble */}
                <div className="flex justify-end">
                  <div className="max-w-xl rounded-2xl rounded-br-md px-4 py-2.5 text-[14px] text-white" style={{ background: "linear-gradient(135deg, #4f46e5 0%, #6366f1 100%)" }}>
                    {entry.question}
                  </div>
                </div>

                {/* Response */}
                <div className="flex justify-start">
                  <div className="max-w-full w-full space-y-3">
                    {entry.success ? (
                      <>
                        {/* SQL Block */}
                        <div className="rounded-xl overflow-hidden border border-white/[0.06]" style={{ background: "rgba(15,20,35,0.6)" }}>
                          <div className="flex items-center justify-between px-4 py-2 border-b border-white/[0.04]">
                            <span className="text-[10px] font-medium text-white/40 uppercase tracking-widest">Generated SQL</span>
                            <button onClick={() => copySQL(entry.sql || "", i)} className="text-[10px] text-white/40 hover:text-white/60 transition flex items-center gap-1">
                              {copied === i ? <><CheckIcon /> Copied</> : "Copy"}
                            </button>
                          </div>
                          <pre className="px-4 py-3 text-[13px] leading-relaxed overflow-x-auto" style={{ color: "#93c5fd" }}>{entry.sql}</pre>
                        </div>

                        {/* Metric Display */}
                        {isSingleMetric(entry) && entry.data && (
                          <div className="flex gap-3">
                            {entry.columns.map((col) => (
                              <div key={col} className="flex-1 rounded-xl px-5 py-4 border border-white/[0.06]" style={{ background: "linear-gradient(135deg, rgba(99,102,241,0.08) 0%, rgba(139,92,246,0.04) 100%)" }}>
                                <p className="text-[10px] text-white/45 uppercase tracking-widest mb-1">{col.replace(/_/g, " ")}</p>
                                <p className="text-[28px] font-semibold text-white/90 tracking-tight" style={{ fontFamily: "'SF Mono', 'Fira Code', monospace" }}>
                                  {formatNumber(entry.data![0][col])}
                                </p>
                              </div>
                            ))}
                          </div>
                        )}

                        {/* Table */}
                        {entry.data && entry.data.length > 1 && (
                          <div className="rounded-xl overflow-hidden border border-white/[0.06]" style={{ background: "rgba(15,20,35,0.4)" }}>
                            <div className="overflow-x-auto">
                              <table className="w-full">
                                <thead>
                                  <tr className="border-b border-white/[0.06]">
                                    {entry.columns.map((col) => (
                                      <th key={col} className="text-left px-4 py-2.5 text-[10px] font-medium text-white/45 uppercase tracking-widest whitespace-nowrap">{col.replace(/_/g, " ")}</th>
                                    ))}
                                  </tr>
                                </thead>
                                <tbody>
                                  {entry.data.slice(0, 20).map((row, ri) => (
                                    <tr key={ri} className="border-b border-white/[0.03] hover:bg-white/[0.02] transition-colors">
                                      {entry.columns.map((col) => (
                                        <td key={col} className="px-4 py-2 text-[13px] text-white/80 whitespace-nowrap">{formatNumber(row[col])}</td>
                                      ))}
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            </div>
                            {entry.row_count > 20 && (
                              <div className="px-4 py-2 border-t border-white/[0.04]">
                                <p className="text-[11px] text-white/35">Showing 20 of {entry.row_count.toLocaleString()} rows</p>
                              </div>
                            )}
                          </div>
                        )}

                        {/* Footer */}
                        <div className="flex items-start gap-4">
                          <span className="text-[11px] text-white/30 pt-1 shrink-0">
                            {entry.row_count.toLocaleString()} {entry.row_count === 1 ? "row" : "rows"}
                          </span>

                          {entry.explanation ? (
                            <ExplanationCard text={entry.explanation} />
                          ) : (
                            <button onClick={() => explainQuery(i)} disabled={explaining === i} className="text-[11px] text-white/40 hover:text-indigo-400/80 transition-colors flex items-center gap-1 pt-1">
                              {explaining === i ? (
                                <span className="flex items-center gap-2">
                                  <span className="flex gap-0.5">
                                    <span className="w-1 h-1 rounded-full bg-indigo-400/60 animate-bounce" style={{ animationDelay: "0ms" }} />
                                    <span className="w-1 h-1 rounded-full bg-indigo-400/60 animate-bounce" style={{ animationDelay: "150ms" }} />
                                    <span className="w-1 h-1 rounded-full bg-indigo-400/60 animate-bounce" style={{ animationDelay: "300ms" }} />
                                  </span>
                                  Explaining
                                </span>
                              ) : (
                                <><ChevronIcon open={false} /> Explain this query</>
                              )}
                            </button>
                          )}
                        </div>
                      </>
                    ) : (
                      <div className="rounded-xl px-4 py-3 border border-red-500/10 text-[13px] text-red-400/70" style={{ background: "rgba(239,68,68,0.04)" }}>
                        {entry.error}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ))}

            {/* Loading */}
            {loading && (
              <div className="flex justify-start animate-slideUp">
                <div className="rounded-xl px-4 py-3 border border-white/[0.06]" style={{ background: "rgba(15,20,35,0.4)" }}>
                  <div className="flex items-center gap-2">
                    <div className="flex gap-1">
                      <div className="w-1.5 h-1.5 rounded-full bg-indigo-400/60 animate-bounce" style={{ animationDelay: "0ms" }} />
                      <div className="w-1.5 h-1.5 rounded-full bg-indigo-400/60 animate-bounce" style={{ animationDelay: "150ms" }} />
                      <div className="w-1.5 h-1.5 rounded-full bg-indigo-400/60 animate-bounce" style={{ animationDelay: "300ms" }} />
                    </div>
                    <span className="text-[12px] text-white/40">Generating SQL...</span>
                  </div>
                </div>
              </div>
            )}

            <div ref={chatEndRef} />
          </div>
        </div>

        {/* Input */}
        <div className="shrink-0 border-t border-white/[0.04] px-4 py-3" style={{ background: "rgba(10,14,26,0.8)", backdropFilter: "blur(20px)" }}>
          <div className="max-w-3xl mx-auto">
            <div className="flex items-center gap-2 rounded-xl border border-white/[0.08] px-4 transition-colors focus-within:border-indigo-500/30" style={{ background: "rgba(255,255,255,0.02)" }}>
              <input
                ref={inputRef}
                type="text"
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && askQuestion(question)}
                placeholder="Ask a question about your database..."
                className="flex-1 bg-transparent py-3 text-[14px] text-white/80 placeholder:text-white/30 focus:outline-none"
                disabled={loading}
              />
              <button onClick={() => askQuestion(question)} disabled={loading || !question.trim()} className="w-8 h-8 flex items-center justify-center rounded-lg transition-all disabled:opacity-20 text-white/40 hover:text-white hover:bg-indigo-500/20">
                <SendIcon />
              </button>
            </div>
            <p className="text-center text-[10px] text-white/20 mt-2">QueryGenie generates SQL from natural language — always verify results</p>
          </div>
        </div>
      </main>

      {/* Animations */}
      <style jsx global>{`
        @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
        @keyframes slideUp { from { opacity: 0; transform: translateY(12px); } to { opacity: 1; transform: translateY(0); } }
        @keyframes slideDown { from { opacity: 0; max-height: 0; } to { opacity: 1; max-height: 500px; } }
        .animate-fadeIn { animation: fadeIn 0.5s ease-out; }
        .animate-slideUp { animation: slideUp 0.35s ease-out; }
        .animate-slideDown { animation: slideDown 0.3s ease-out; }
        .scrollbar-thin::-webkit-scrollbar { width: 4px; }
        .scrollbar-thin::-webkit-scrollbar-track { background: transparent; }
        .scrollbar-thin::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.06); border-radius: 4px; }
        * { scrollbar-width: thin; scrollbar-color: rgba(255,255,255,0.06) transparent; }
        select { -moz-appearance: none; }
      `}</style>
    </div>
  );
}

/* ═══════════ Sub-components ═══════════ */

function SchemaTable({ name, block }: { name: string; block: string }) {
  const [open, setOpen] = useState(false);
  const columns = block.match(/- (.+)/g)?.map((l) => l.replace("- ", "").trim()) || [];

  return (
    <div className="rounded-lg border border-white/[0.04] overflow-hidden">
      <button onClick={() => setOpen(!open)} className="w-full flex items-center gap-2 px-3 py-1.5 text-[11px] text-white/60 hover:text-white/80 hover:bg-white/[0.02] transition">
        <ChevronIcon open={open} />
        <span className="font-mono text-indigo-400/80">{name}</span>
      </button>
      {open && (
        <div className="px-3 pb-2 space-y-0.5">
          {columns.slice(0, 15).map((col, i) => (
            <p key={i} className="text-[10px] text-white/40 font-mono truncate pl-4">{col}</p>
          ))}
        </div>
      )}
    </div>
  );
}

function ExplanationCard({ text }: { text: string }) {
  const parts = parseExplanation(text);

  return (
    <div className="flex-1 rounded-xl border border-white/[0.04] overflow-hidden" style={{ background: "rgba(15,20,35,0.3)" }}>
      <div className="px-4 py-2 border-b border-white/[0.04]">
        <p className="text-[10px] text-indigo-400/70 uppercase tracking-widest font-medium">Query Explanation</p>
      </div>
      <div className="px-4 py-3 space-y-2">
        {parts.length === 1 ? (
          <p className="text-[12px] text-white/60 leading-relaxed">{parts[0]}</p>
        ) : (
          parts.map((part, i) => (
            <div key={i} className="flex gap-2.5">
              <div className="shrink-0 w-5 h-5 rounded-full flex items-center justify-center text-[9px] font-medium mt-0.5" style={{ background: "rgba(99,102,241,0.1)", color: "rgba(129,140,248,0.8)" }}>
                {i + 1}
              </div>
              <p className="text-[12px] text-white/60 leading-relaxed">{part}</p>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
