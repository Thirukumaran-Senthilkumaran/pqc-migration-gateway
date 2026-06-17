import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Circle, Hammer, RotateCcw, AlertTriangle } from "lucide-react";
import {
  fetchMigrationPlan, MigrationStageOut, rebuildPlan, StageStatus, updateStage,
} from "../api/client";

const stageIcon: Record<StageStatus, JSX.Element> = {
  planned:     <Circle className="size-4 text-muted" />,
  in_progress: <Hammer className="size-4 text-accent-glow" />,
  completed:   <CheckCircle2 className="size-4 text-emerald-400" />,
  blocked:     <AlertTriangle className="size-4 text-red-400" />,
};

export default function Migration() {
  const qc = useQueryClient();
  const { data } = useQuery({
    queryKey: ["plan"],
    queryFn: fetchMigrationPlan,
    refetchInterval: 6_000,
  });

  const m_rebuild = useMutation({
    mutationFn: rebuildPlan,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["plan"] }),
  });
  const m_update = useMutation({
    mutationFn: ({ id, status }: { id: number; status: StageStatus }) => updateStage(id, status),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["plan"] }),
  });

  const stages = data?.stages ?? [];

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Migration Plan</h1>
          <p className="text-muted text-sm mt-1">
            Stage-by-stage rollout of native PQC across the LAN. The gateway covers everyone in between.
          </p>
        </div>
        <button onClick={() => m_rebuild.mutate()} className="btn-ghost">
          <RotateCcw className="size-4" />
          Rebuild from current classification
        </button>
      </div>

      <div className="space-y-4">
        {stages.map((stage) => (
          <StageCard
            key={stage.id}
            stage={stage}
            taskCount={
              data?.tasks.filter((t) => t.stage_id === stage.id).length ?? 0
            }
            onChangeStatus={(status) =>
              m_update.mutate({ id: stage.id, status })
            }
          />
        ))}
      </div>
    </div>
  );
}

function StageCard({
  stage,
  taskCount,
  onChangeStatus,
}: {
  stage: MigrationStageOut;
  taskCount: number;
  onChangeStatus: (s: StageStatus) => void;
}) {
  return (
    <div className="card p-5">
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="size-9 rounded-lg bg-bg-soft border border-bg-border grid place-items-center font-mono text-xs">
            {stage.ordinal}
          </div>
          <div>
            <div className="font-semibold flex items-center gap-2">
              {stageIcon[stage.status]} {stage.name}
              {stage.target_tier && (
                <span className="badge-muted">{stage.target_tier}</span>
              )}
            </div>
            <div className="text-xs text-muted mt-0.5">{stage.description}</div>
          </div>
        </div>
        <div className="text-right">
          <div className="text-xs text-muted">{taskCount} task{taskCount === 1 ? "" : "s"}</div>
          <div className="text-sm font-mono">{stage.progress_pct.toFixed(1)}%</div>
        </div>
      </div>

      <div className="mt-3 h-2 bg-bg-soft rounded-full overflow-hidden border border-bg-border">
        <div
          className="h-full bg-gradient-to-r from-accent to-accent-glow"
          style={{ width: `${stage.progress_pct}%` }}
        />
      </div>

      <div className="mt-3 flex gap-2">
        {(["planned", "in_progress", "completed", "blocked"] as StageStatus[]).map((s) => (
          <button
            key={s}
            onClick={() => onChangeStatus(s)}
            className={
              stage.status === s
                ? "btn-primary text-xs px-2 py-1"
                : "btn-ghost text-xs px-2 py-1"
            }
          >
            {s.replace("_", " ")}
          </button>
        ))}
      </div>
    </div>
  );
}
