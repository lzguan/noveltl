import { useEffect, useState, useCallback, useRef } from "react";
import { useLanguages } from "../../contexts/LanguageContext";
import {
    createNovelTranslation,
    getNovelTranslationJob,
    getNovelTranslationJobs,
} from "../../api/translations";
import type * as TranslationType from "../../types/translation";
import { NovelTranslationStatus } from "../../types/translation";
import type * as GlossaryType from "../../types/glossary";
import { routeTo } from "../../routes";

// ---- TranslationPanel ----

interface TranslationPanelProps {
    novelId: string;
    glossaries?: GlossaryType.Glossary[];
}

export const TranslationPanel = ({ novelId, glossaries = [] }: TranslationPanelProps) => {
    const languages = useLanguages();

    // Form state
    const [targetLanguageCode, setTargetLanguageCode] = useState("");
    const [selectedGlossaryId, setSelectedGlossaryId] = useState<string>("");
    const [formError, setFormError] = useState<string | null>(null);
    const [submitting, setSubmitting] = useState(false);

    // Active job state
    const [activeJob, setActiveJob] = useState<TranslationType.NovelTranslationJob | null>(null);
    const [translationError, setTranslationError] = useState<string | null>(null);
    const [translationSuccess, setTranslationSuccess] = useState(false);
    const pollIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

    // History state
    const [pastJobs, setPastJobs] = useState<TranslationType.NovelTranslationJob[]>([]);
    const [historyOpen, setHistoryOpen] = useState(false);
    const [historyLoading, setHistoryLoading] = useState(false);

    // Stop polling on unmount
    useEffect(() => {
        return () => {
            if (pollIntervalRef.current !== null) {
                clearInterval(pollIntervalRef.current);
            }
        };
    }, []);

    const stopPolling = useCallback(() => {
        if (pollIntervalRef.current !== null) {
            clearInterval(pollIntervalRef.current);
            pollIntervalRef.current = null;
        }
    }, []);

    const startPolling = useCallback((jobId: string) => {
        stopPolling();
        pollIntervalRef.current = setInterval(() => {
            getNovelTranslationJob(jobId)
                .then((job) => {
                    setActiveJob(job);
                    if (job.status === NovelTranslationStatus.done) {
                        stopPolling();
                        setTranslationSuccess(true);
                    } else if (job.status === NovelTranslationStatus.failed) {
                        stopPolling();
                        setTranslationError(job.jobMessage ?? "Translation failed.");
                    }
                })
                .catch((err) => {
                    console.error(err);
                    stopPolling();
                    setTranslationError("Failed to poll translation status.");
                });
        }, 4000);
    }, [stopPolling]);

    const handleTranslate = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!targetLanguageCode) {
            setFormError("Target language is required.");
            return;
        }
        setFormError(null);
        setTranslationError(null);
        setTranslationSuccess(false);
        setSubmitting(true);
        try {
            const job = await createNovelTranslation({
                sourceNovelId: novelId,
                targetLanguageCode,
                glossaryId: selectedGlossaryId || null,
                modelName: null,
            });
            setActiveJob(job);
            if (job.status === NovelTranslationStatus.done) {
                setTranslationSuccess(true);
            } else if (job.status === NovelTranslationStatus.failed) {
                setTranslationError(job.jobMessage ?? "Translation failed.");
            } else {
                startPolling(job.jobId);
            }
        } catch (err) {
            console.error(err);
            setTranslationError("Failed to start translation.");
        } finally {
            setSubmitting(false);
        }
    };

    const handleLoadHistory = async () => {
        setHistoryLoading(true);
        try {
            const jobs = await getNovelTranslationJobs(novelId);
            setPastJobs(jobs);
            setHistoryOpen(true);
        } catch (err) {
            console.error(err);
        } finally {
            setHistoryLoading(false);
        }
    };

    const isTranslating =
        activeJob !== null &&
        (activeJob.status === NovelTranslationStatus.pending ||
            activeJob.status === NovelTranslationStatus.processing);

    const statusColor = (status: TranslationType.NovelTranslationStatus) => {
        if (status === NovelTranslationStatus.done) return "#2e7d32";
        if (status === NovelTranslationStatus.failed) return "#c00";
        if (status === NovelTranslationStatus.processing) return "#1565c0";
        return "#555";
    };

    return (
        <div style={{ padding: "10px", display: "flex", flexDirection: "column", gap: "12px" }}>
            <div style={{ fontWeight: 600, fontSize: "0.9rem" }}>Translate Novel</div>

            {/* Translation form */}
            <form onSubmit={(e) => void handleTranslate(e)} style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                {formError && (
                    <div style={{ color: "#c00", fontSize: "0.82rem" }}>{formError}</div>
                )}

                <div>
                    <label style={{ display: "block", marginBottom: "3px", fontWeight: 500, fontSize: "0.82rem" }}>
                        Target Language *
                    </label>
                    <select
                        value={targetLanguageCode}
                        onChange={(e) => setTargetLanguageCode(e.target.value)}
                        style={{ width: "100%", padding: "5px 4px", borderRadius: "4px", border: "1px solid #ccc", fontSize: "0.85rem" }}
                    >
                        <option value="">Select...</option>
                        {languages.map((l) => (
                            <option key={l.languageCode} value={l.languageCode}>
                                {l.languageName}
                            </option>
                        ))}
                    </select>
                </div>

                {glossaries.length > 0 && (
                    <div>
                        <label style={{ display: "block", marginBottom: "3px", fontWeight: 500, fontSize: "0.82rem" }}>
                            Glossary (optional)
                        </label>
                        <select
                            value={selectedGlossaryId}
                            onChange={(e) => setSelectedGlossaryId(e.target.value)}
                            style={{ width: "100%", padding: "5px 4px", borderRadius: "4px", border: "1px solid #ccc", fontSize: "0.85rem" }}
                        >
                            <option value="">None</option>
                            {glossaries.map((g) => (
                                <option key={g.glossaryId} value={g.glossaryId}>
                                    {g.glossaryName}
                                </option>
                            ))}
                        </select>
                    </div>
                )}

                <button
                    type="submit"
                    disabled={submitting || isTranslating}
                    style={{
                        padding: "5px 12px",
                        borderRadius: "4px",
                        border: "none",
                        cursor: submitting || isTranslating ? "default" : "pointer",
                        background: submitting || isTranslating ? "#aaa" : "#4a90d9",
                        color: "#fff",
                        fontWeight: 500,
                        fontSize: "0.85rem",
                        opacity: submitting || isTranslating ? 0.7 : 1,
                        alignSelf: "flex-start",
                    }}
                >
                    {submitting ? "Starting..." : isTranslating ? "Translating..." : "Translate"}
                </button>
            </form>

            {/* Active job progress */}
            {isTranslating && activeJob && (
                <div style={{ fontSize: "0.82rem", color: "#1565c0", padding: "8px 10px", background: "#e3f2fd", borderRadius: "4px" }}>
                    <div style={{ marginBottom: "6px" }}>
                        Translating... {activeJob.chaptersTranslated}/{activeJob.chaptersTotal} chapters
                    </div>
                    <div style={{ background: "#bbdefb", borderRadius: "3px", height: "6px", overflow: "hidden" }}>
                        <div
                            style={{
                                width: activeJob.chaptersTotal > 0
                                    ? `${Math.round((activeJob.chaptersTranslated / activeJob.chaptersTotal) * 100)}%`
                                    : "0%",
                                height: "100%",
                                background: "#1565c0",
                                transition: "width 0.3s ease",
                            }}
                        />
                    </div>
                    <div style={{ marginTop: "4px", color: "#888" }}>Status: {activeJob.status}</div>
                </div>
            )}

            {/* Translation success */}
            {translationSuccess && activeJob && (
                <div style={{ fontSize: "0.82rem", color: "#2e7d32", padding: "8px 10px", background: "#e8f5e9", borderRadius: "4px" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                        <div>
                            <div style={{ fontWeight: 500 }}>Translation complete</div>
                            <div style={{ color: "#555", marginTop: "2px" }}>
                                {activeJob.chaptersTranslated}/{activeJob.chaptersTotal} chapters translated
                            </div>
                        </div>
                        <button
                            onClick={() => { setTranslationSuccess(false); setActiveJob(null); }}
                            style={{ background: "none", border: "none", cursor: "pointer", color: "#666", fontSize: "0.8rem", flexShrink: 0 }}
                        >
                            x
                        </button>
                    </div>
                    {activeJob.targetNovelId && (
                        <a
                            href={routeTo.workspace(activeJob.targetNovelId)}
                            style={{ display: "inline-block", marginTop: "6px", padding: "3px 8px", borderRadius: "4px", background: "#2e7d32", color: "#fff", fontSize: "0.8rem", textDecoration: "none" }}
                        >
                            Open translated novel
                        </a>
                    )}
                </div>
            )}

            {/* Translation error */}
            {translationError && (
                <div style={{ fontSize: "0.82rem", color: "#c00", padding: "8px 10px", background: "#fff0f0", borderRadius: "4px", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <span>Error: {translationError}</span>
                    <button
                        onClick={() => { setTranslationError(null); setActiveJob(null); }}
                        style={{ background: "none", border: "none", cursor: "pointer", color: "#666", fontSize: "0.8rem", flexShrink: 0 }}
                    >
                        x
                    </button>
                </div>
            )}

            {/* History button and list */}
            <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
                <button
                    onClick={() => void handleLoadHistory()}
                    disabled={historyLoading}
                    style={{ padding: "4px 8px", borderRadius: "4px", border: "1px solid #ccc", cursor: "pointer", background: "#fff", fontSize: "0.78rem", color: "#555", alignSelf: "flex-start" }}
                >
                    {historyLoading ? "Loading..." : "Job History"}
                </button>

                {historyOpen && (
                    <div style={{ border: "1px solid #e0e0e0", borderRadius: "4px", padding: "8px", background: "#fafafa" }}>
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "6px" }}>
                            <span style={{ fontWeight: 600, fontSize: "0.82rem" }}>Translation Jobs</span>
                            <button
                                onClick={() => setHistoryOpen(false)}
                                style={{ background: "none", border: "none", cursor: "pointer", color: "#888", fontSize: "0.8rem" }}
                            >
                                x
                            </button>
                        </div>
                        {pastJobs.length === 0 ? (
                            <div style={{ fontSize: "0.78rem", color: "#888" }}>No jobs yet.</div>
                        ) : (
                            <div style={{ display: "flex", flexDirection: "column", gap: "4px", maxHeight: "200px", overflowY: "auto" }}>
                                {pastJobs.map((job) => (
                                    <div
                                        key={job.jobId}
                                        style={{ fontSize: "0.78rem", padding: "6px 8px", border: "1px solid #eee", borderRadius: "3px", background: "#fff" }}
                                    >
                                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                                            <span style={{ fontWeight: 500, color: statusColor(job.status) }}>
                                                {job.status}
                                            </span>
                                            <span style={{ color: "#888" }}>
                                                {new Date(job.createdAt).toLocaleDateString()}
                                            </span>
                                        </div>
                                        <div style={{ color: "#555", marginTop: "2px" }}>
                                            {job.chaptersTranslated}/{job.chaptersTotal} chapters
                                            {job.targetLanguageCode && (
                                                <span style={{ marginLeft: "6px", background: "#eee", borderRadius: "3px", padding: "1px 4px" }}>
                                                    {job.targetLanguageCode}
                                                </span>
                                            )}
                                        </div>
                                        {job.jobMessage && (
                                            <div style={{ color: "#c00", marginTop: "2px" }}>{job.jobMessage}</div>
                                        )}
                                        {job.status === NovelTranslationStatus.done && job.targetNovelId && (
                                            <a
                                                href={routeTo.workspace(job.targetNovelId)}
                                                style={{ display: "inline-block", marginTop: "4px", color: "#1565c0", fontSize: "0.76rem", textDecoration: "underline" }}
                                            >
                                                Open translated novel
                                            </a>
                                        )}
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                )}
            </div>
        </div>
    );
};
