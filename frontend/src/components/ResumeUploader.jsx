import React, { useRef, useState } from "react";
import {
  AlertCircle,
  CheckCircle2,
  FileText,
  UploadCloud,
} from "lucide-react";
// eslint-disable-next-line no-unused-vars
import { motion } from "framer-motion";
import { animate, eases, spring } from "animejs";
import { clsx } from "clsx";
import VectorProcessingLoader from "./VectorProcessingLoader";

const INGEST_ENDPOINT = "https://api.resuresq.app/api/ingest";
const DEFAULT_BORDER_COLOR = "rgba(255, 255, 255, 0.2)";
const DEFAULT_BOX_SHADOW = "0px 0px 0px rgba(212, 175, 55, 0)";

export default function ResumeUploader({ onUploadSuccess }) {
  const [status, setStatus] = useState("idle");
  const [message, setMessage] = useState("");
  const [fileName, setFileName] = useState("");
  const [isDragging, setIsDragging] = useState(false);
  const [file, setFile] = useState(null);
  const inputRef = useRef(null);
  const dropzoneRef = useRef(null);
  const dragDepthRef = useRef(0);
  const animationRef = useRef(null);

  const isUploading = status === "uploading" || status === "processing";

  const runDropzoneAnimation = (params) => {
    if (!dropzoneRef.current) return;
    animationRef.current?.cancel?.();
    animationRef.current = animate(dropzoneRef.current, params);
  };

  const resetDropzoneAnimation = () => {
    runDropzoneAnimation({
      scale: 1,
      borderColor: DEFAULT_BORDER_COLOR,
      boxShadow: DEFAULT_BOX_SHADOW,
      duration: 300,
      ease: eases.outQuad,
    });
  };

  const showInvalidFileError = (selectedFile) => {
    setStatus("error");
    setMessage("Only PDF resumes can be uploaded.");
    setFileName(selectedFile?.name || "");
    setFile(null);
  };

  const handleUpload = async (selectedFile) => {
    if (!selectedFile) return;

    if (
      selectedFile.type !== "application/pdf" ||
      !selectedFile.name.toLowerCase().endsWith(".pdf")
    ) {
      showInvalidFileError(selectedFile);
      return;
    }

    setFile(selectedFile);
    setStatus("uploading");
    setMessage("Uploading resume...");
    setFileName(selectedFile.name);

    try {
      const formData = new FormData();
      formData.append("file", selectedFile);

      setStatus("processing");
      setMessage("Processing resume...");

      const response = await fetch(INGEST_ENDPOINT, {
        method: "POST",
        body: formData,
      });

      const payload = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(payload.detail || "Resume ingestion failed.");
      }

      setStatus("success");
      setMessage(`${payload.chunks_processed ?? 0} chunks indexed.`);
      onUploadSuccess?.(payload);
    } catch (error) {
      setStatus("error");
      setMessage(error.message || "Resume upload failed.");
    } finally {
      if (inputRef.current) {
        inputRef.current.value = "";
      }
    }
  };

  const handleFileChange = (event) => {
    handleUpload(event.target.files?.[0]);
  };

  const handleDragOver = (event) => {
    event.preventDefault();
  };

  const handleDragEnter = (event) => {
    event.preventDefault();
    dragDepthRef.current += 1;
    setIsDragging(true);
    runDropzoneAnimation({
      scale: 1.04,
      borderColor: "var(--color-gold)",
      boxShadow: "0px 0px 24px rgba(212, 175, 55, 0.22)",
      duration: 400,
      ease: eases.outElastic(1, 0.6),
    });
  };

  const handleDragLeave = (event) => {
    event.preventDefault();
    dragDepthRef.current = Math.max(0, dragDepthRef.current - 1);
    if (dragDepthRef.current > 0) return;
    setIsDragging(false);
    resetDropzoneAnimation();
  };

  const handleDrop = (event) => {
    event.preventDefault();
    dragDepthRef.current = 0;
    setIsDragging(false);

    const droppedFile = event.dataTransfer.files?.[0];
    if (!droppedFile) {
      resetDropzoneAnimation();
      return;
    }

    if (droppedFile.type !== "application/pdf") {
      showInvalidFileError(droppedFile);
      resetDropzoneAnimation();
      return;
    }

    runDropzoneAnimation({
      scale: [1.04, 0.95, 1],
      duration: 600,
      ease: spring(1, 80, 10, 0),
    });
    handleUpload(droppedFile);
  };

  return (
    <motion.section
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      className="mb-8"
    >
      <div
        ref={dropzoneRef}
        onDragOver={handleDragOver}
        onDragEnter={handleDragEnter}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        className={clsx(
          "relative w-full max-w-lg mx-auto p-6 border-2 border-dashed rounded-3xl backdrop-blur-md text-center transition-all duration-300 bg-white/40 dark:bg-slate-900/50 border-white/20 dark:border-white/10 hover:bg-white/60 dark:hover:bg-slate-900/70",
          isDragging && "bg-white/70 dark:bg-slate-900/80",
        )}
      >
        <div className="mx-auto mb-5 flex h-16 w-16 items-center justify-center rounded-2xl bg-white/70 text-gold-dark ring-1 ring-gold/30 dark:bg-zinc-900/70 dark:text-gold dark:ring-gold/20">
          {status === "success" ? (
            <CheckCircle2 size={30} />
          ) : status === "error" ? (
            <AlertCircle size={30} />
          ) : (
            <UploadCloud size={30} />
          )}
        </div>

        <div className="space-y-2">
          <h2 className="text-2xl font-bold tracking-tight text-zinc-950 dark:text-slate-100">
            {fileName || "Drop a PDF resume here"}
          </h2>
          <p
            className={clsx(
              "mx-auto max-w-md text-sm leading-6",
              status === "error"
                ? "text-red-600 dark:text-red-400"
                : status === "success"
                  ? "text-emerald-600 dark:text-emerald-400"
                  : "text-zinc-600 dark:text-slate-400",
            )}
          >
            {message ||
              "Drag and drop a resume, or browse files to ingest it into the candidate index."}
          </p>
        </div>

        {isUploading && <VectorProcessingLoader />}

        <div className="mt-7 flex flex-col items-center justify-center gap-3 sm:flex-row">
          <input
            ref={inputRef}
            type="file"
            accept=".pdf"
            disabled={isUploading}
            onChange={handleFileChange}
            className="hidden"
            id="resume-upload-input"
          />
          <button
            type="button"
            disabled={isUploading}
            onClick={() => inputRef.current?.click()}
            className={clsx(
              "inline-flex items-center gap-2 rounded-xl border border-gold/30 bg-white/80 px-5 py-3 text-sm font-semibold text-gold-dark shadow-sm transition-colors dark:bg-zinc-900/80 dark:text-gold",
              isUploading
                ? "cursor-not-allowed opacity-60"
                : "hover:bg-white dark:hover:bg-zinc-900 focus:outline-none focus:ring-2 focus:ring-gold/40",
            )}
          >
            <FileText size={16} />
            Browse Files
          </button>
          {file && (
            <span className="max-w-xs truncate text-xs font-medium text-slate-500 dark:text-slate-400">
              Selected: {file.name}
            </span>
          )}
        </div>
      </div>
    </motion.section>
  );
}
