"use client";

import { useEffect, useState } from "react";
import { Archive, ChevronLeft, EyeOff, Loader2, X } from "lucide-react";
import {
  fetchChildEssayArchive,
  hideChildEssay,
} from "../../lib/api";
import type { EssayArchiveItem } from "../../lib/types";

type EssayArchiveDrawerProps = {
  studentId: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSelectEssay: (essayId: string) => void;
};

type ArchiveLoadState = {
  studentId: string | null;
  items: EssayArchiveItem[];
  error: string;
};

export function EssayArchiveDrawer({
  studentId,
  open,
  onOpenChange,
  onSelectEssay,
}: EssayArchiveDrawerProps) {
  const [archiveState, setArchiveState] = useState<ArchiveLoadState>({
    studentId: null,
    items: [],
    error: "",
  });

  useEffect(() => {
    if (!open) {
      return;
    }

    let active = true;
    fetchChildEssayArchive(studentId, 3)
      .then((result) => {
        if (!active) {
          return;
        }
        setArchiveState({
          studentId,
          items: result.items.slice(0, 3),
          error: "",
        });
      })
      .catch(() => {
        if (active) {
          setArchiveState((current) => ({
            studentId,
            items: current.studentId === studentId ? current.items : [],
            error: "档案暂时没有打开，等一下再试。",
          }));
        }
      });

    return () => {
      active = false;
    };
  }, [open, studentId]);

  const isCurrentStudentArchive = archiveState.studentId === studentId;
  const items = isCurrentStudentArchive ? archiveState.items : [];
  const error = isCurrentStudentArchive ? archiveState.error : "";
  const isLoading = open && !isCurrentStudentArchive;

  async function handleHideEssay(essayId: string) {
    try {
      await hideChildEssay(essayId);
      setArchiveState((current) => ({
        ...current,
        error: "",
        items: current.items.filter((item) => item.essay_id !== essayId),
      }));
    } catch {
      setArchiveState((current) => ({
        ...current,
        error: "这篇暂时没有藏起来，可以稍后再试。",
      }));
    }
  }

  return (
    <>
      {open ? (
        <button
          aria-label="收起作文档案"
          className="fixed inset-0 z-30 bg-black/20"
          type="button"
          onClick={() => onOpenChange(false)}
        />
      ) : null}
      <aside
        aria-hidden={open ? "false" : "true"}
        aria-label="作文档案"
        className={`fixed right-0 top-0 z-40 h-screen w-[min(92vw,380px)] border-l border-[var(--wen-border)] bg-white shadow-xl transition-transform duration-200 sm:w-[min(64vw,420px)] lg:w-[360px] ${
          open ? "translate-x-0" : "translate-x-full"
        }`}
        role="complementary"
      >
        {open ? (
          <div className="flex h-full flex-col">
            <div className="flex items-center justify-between border-b border-[var(--wen-border)] px-4 py-4">
              <div className="flex items-center gap-2 font-bold">
                <Archive size={20} aria-hidden="true" className="text-[var(--wen-orange)]" />
                作文档案
              </div>
              <button
                aria-label="关闭作文档案"
                className="rounded-lg border border-[var(--wen-border)] p-2"
                type="button"
                onClick={() => onOpenChange(false)}
              >
                <X size={18} aria-hidden="true" />
              </button>
            </div>

            <div className="flex-1 space-y-3 overflow-y-auto p-4">
              {isLoading ? (
                <p className="flex items-center gap-2 font-semibold" role="status">
                  <Loader2 size={18} aria-hidden="true" className="animate-spin" />
                  正在找最近的作文
                </p>
              ) : null}
              {error ? (
                <p className="rounded-lg border border-[var(--wen-orange)] p-3 font-semibold" role="alert">
                  {error}
                </p>
              ) : null}
              {!isLoading && items.length === 0 ? (
                <p className="rounded-lg bg-[var(--wen-bg)] p-3 font-semibold">
                  还没有可继续修改的作文。
                </p>
              ) : null}
              {items.map((item) => (
                <div
                  className="rounded-lg border border-[var(--wen-border)] bg-[var(--wen-bg)] p-3"
                  key={item.essay_id}
                >
                  <button
                    className="flex w-full items-center justify-between gap-3 text-left disabled:cursor-not-allowed disabled:opacity-60"
                    disabled={!item.can_continue_revision}
                    type="button"
                    onClick={() => onSelectEssay(item.essay_id)}
                  >
                    <span>
                      <span className="block font-bold">{item.title || "未命名作文"}</span>
                      <span className="mt-1 block text-sm text-[var(--wen-muted)]">
                        {item.summary_label}
                      </span>
                      {!item.can_continue_revision ? (
                        <span className="mt-1 block text-sm font-semibold text-[var(--wen-muted)]">
                          这篇暂时不能继续修改
                        </span>
                      ) : null}
                    </span>
                    <ChevronLeft size={18} aria-hidden="true" />
                  </button>
                  <button
                    aria-label="暂时藏起这篇作文"
                    className="mt-3 inline-flex items-center gap-1 text-sm font-semibold text-[var(--wen-muted)]"
                    type="button"
                    onClick={() => handleHideEssay(item.essay_id)}
                  >
                    <EyeOff size={16} aria-hidden="true" />
                    暂时藏起来
                  </button>
                </div>
              ))}
            </div>
          </div>
        ) : null}
      </aside>
    </>
  );
}
