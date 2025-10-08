import type { ColDef, ColGroupDef } from "ag-grid-community";
import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import IconComponent from "@/components/common/genericIconComponent";
import PaginatorComponent from "@/components/common/paginatorComponent";
import TableComponent from "@/components/core/parameterRenderComponent/components/tableComponent";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useGetWorkspaces } from "@/controllers/API/queries/ai/use-get-workspaces";
import { useResumeCodegen } from "@/controllers/API/queries/ai/use-resume-codegen";
import { useDeleteWorkspace } from "@/controllers/API/queries/ai/use-workspace-ops";
import { useGetTransactionsQuery } from "@/controllers/API/queries/transactions";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { convertUTCToLocalTimezone } from "@/utils/utils";
import BaseModal from "../baseModal";

export default function FlowLogsModal({
  children,
}: {
  children: React.ReactNode;
}): JSX.Element {
  const currentFlowId = useFlowsManagerStore((state) => state.currentFlowId);
  const [open, setOpen] = useState(false);

  const [pageIndex, setPageIndex] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [columns, setColumns] = useState<Array<ColDef | ColGroupDef>>([]);
  const [rows, setRows] = useState<any>([]);
  const [searchParams] = useSearchParams();
  const flowIdFromUrl = searchParams.get("id");

  const { data, isLoading, refetch } = useGetTransactionsQuery({
    id: currentFlowId ?? flowIdFromUrl,
    params: {
      page: pageIndex,
      size: pageSize,
    },
    mode: "union",
  });

  // Wasm run history (workspaces) filtered by flow
  const { data: wsList, refetch: refetchWs } = useGetWorkspaces();
  const delOne = useDeleteWorkspace();
  const resumeCodegen = useResumeCodegen();
  const [resumeHint, setResumeHint] = useState("");
  const [selectedWorkspace, setSelectedWorkspace] = useState<any>(null);
  const [resumeDialogOpen, setResumeDialogOpen] = useState(false);

  useEffect(() => {
    if (data) {
      const { columns, rows } = data;

      if (data?.rows?.length > 0) {
        data.rows.map((row: any) => {
          row.timestamp = convertUTCToLocalTimezone(row.timestamp);
        });
      }

      setColumns(columns.map((col) => ({ ...col, editable: true })));
      setRows(rows);
    }
  }, [data]);

  useEffect(() => {
    if (open) {
      refetch();
    }
  }, [open]);

  const handlePageChange = useCallback((newPageIndex, newPageSize) => {
    setPageIndex(newPageIndex);
    setPageSize(newPageSize);
  }, []);

  return (
    <BaseModal open={open} setOpen={setOpen} size="x-large">
      <BaseModal.Trigger asChild>{children}</BaseModal.Trigger>
      <BaseModal.Header description="Inspect component executions and Wasm runs.">
        <div className="flex w-full justify-between">
          <div className="flex h-fit w-32 items-center">
            <span className="pr-2">Logs</span>
            <IconComponent name="ScrollText" className="mr-2 h-4 w-4" />
          </div>
          <div className="flex h-fit w-32 items-center"></div>
        </div>
      </BaseModal.Header>
      <BaseModal.Content>
        <Tabs defaultValue="executions">
          <div className="flex items-center justify-between mb-2">
            <TabsList>
              <TabsTrigger value="executions">Executions</TabsTrigger>
              <TabsTrigger value="wasm">Wasm Runs</TabsTrigger>
            </TabsList>
            <div></div>
          </div>
          <TabsContent value="executions">
            <TableComponent
              key={"Executions"}
              readOnlyEdit
              className="h-max-full h-full w-full"
              pagination={false}
              columnDefs={columns}
              autoSizeStrategy={{ type: "fitGridWidth" }}
              rowData={rows}
              headerHeight={rows.length === 0 ? 0 : undefined}
            ></TableComponent>
            {!isLoading && (data?.pagination.total ?? 0) >= 10 && (
              <div className="flex justify-end px-3 py-4">
                <PaginatorComponent
                  pageIndex={data?.pagination.page ?? 1}
                  pageSize={data?.pagination.size ?? 10}
                  rowsCount={[12, 24, 48, 96]}
                  totalRowsCount={data?.pagination.total ?? 0}
                  paginate={handlePageChange}
                  pages={data?.pagination.pages}
                />
              </div>
            )}
          </TabsContent>
          <TabsContent value="wasm">
            <div className="text-xs">
              <div className="flex items-center justify-between mb-2">
                <div className="text-sm font-semibold">Run history</div>
                <Button size="xs" variant="outline" onClick={() => refetchWs()}>
                  Refresh
                </Button>
              </div>
              <div className="border rounded p-2 space-y-2">
                {(wsList?.workspaces ?? [])
                  .filter(
                    (w) =>
                      !currentFlowId ||
                      !w.flow_id ||
                      w.flow_id === currentFlowId,
                  )
                  .map((w) => (
                    <div
                      key={w.root_b64}
                      className="border rounded p-2 bg-muted/20"
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <span className="font-mono text-xs">{w.name}</span>
                          {w.type && (
                            <span className="px-1.5 py-0.5 rounded bg-muted text-xs">
                              {w.type}
                            </span>
                          )}
                          {w.success != null && (
                            <span
                              className={`px-1.5 py-0.5 rounded text-xs font-semibold ${
                                w.success
                                  ? "bg-green-100 text-green-700"
                                  : "bg-red-100 text-red-700"
                              }`}
                            >
                              {w.success ? "✓ Success" : "✗ Failed"}
                            </span>
                          )}
                        </div>
                        <div className="flex items-center gap-2">
                          {!w.success && w.success != null && (
                            <Dialog
                              open={
                                resumeDialogOpen &&
                                selectedWorkspace?.root_b64 === w.root_b64
                              }
                              onOpenChange={(open) => {
                                setResumeDialogOpen(open);
                                if (!open) setSelectedWorkspace(null);
                              }}
                            >
                              <DialogTrigger asChild>
                                <Button
                                  size="xs"
                                  variant="outline"
                                  onClick={() => {
                                    setSelectedWorkspace(w);
                                    setResumeHint("");
                                    setResumeDialogOpen(true);
                                  }}
                                >
                                  Resume
                                </Button>
                              </DialogTrigger>
                              <DialogContent>
                                <DialogHeader>
                                  <DialogTitle>
                                    Resume codegen with hint
                                  </DialogTitle>
                                  <DialogDescription>
                                    Provide an optional hint to guide the AI in
                                    fixing the issues from the previous run.
                                  </DialogDescription>
                                </DialogHeader>
                                <div className="py-4">
                                  <Input
                                    placeholder="e.g., Check for missing imports or fix the trait implementation"
                                    value={resumeHint}
                                    onChange={(e) =>
                                      setResumeHint(e.target.value)
                                    }
                                  />
                                </div>
                                <DialogFooter>
                                  <Button
                                    variant="outline"
                                    onClick={() => setResumeDialogOpen(false)}
                                  >
                                    Cancel
                                  </Button>
                                  <Button
                                    onClick={async () => {
                                      await resumeCodegen.mutateAsync({
                                        workspace_root_b64: w.root_b64,
                                        user_hint: resumeHint || null,
                                        max_iters: 3,
                                      });
                                      setResumeDialogOpen(false);
                                      setSelectedWorkspace(null);
                                      refetchWs();
                                    }}
                                  >
                                    Resume
                                  </Button>
                                </DialogFooter>
                              </DialogContent>
                            </Dialog>
                          )}
                          <a
                            className="underline text-xs"
                            href={`#/settings/ai-codegen`}
                            target="_blank"
                            rel="noreferrer"
                          >
                            Browse
                          </a>
                          <Button
                            size="xs"
                            variant="destructive"
                            onClick={async () => {
                              await delOne.mutateAsync(w.root_b64);
                              refetchWs();
                            }}
                          >
                            Delete
                          </Button>
                        </div>
                      </div>
                      <div className="mt-1 text-xs text-muted-foreground space-y-0.5">
                        {w.component_id && (
                          <div>Component: {w.component_id}</div>
                        )}
                        {w.started_at && (
                          <div>
                            Started: {new Date(w.started_at).toLocaleString()}
                          </div>
                        )}
                        {w.updated_at && typeof w.updated_at === "number" && (
                          <div>
                            Updated:{" "}
                            {new Date(w.updated_at * 1000).toLocaleString()}
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                {(wsList?.workspaces ?? []).filter(
                  (w) =>
                    !currentFlowId || !w.flow_id || w.flow_id === currentFlowId,
                ).length === 0 && (
                  <div className="text-muted-foreground p-4 text-center">
                    No runs found for this flow.
                  </div>
                )}
              </div>
            </div>
          </TabsContent>
        </Tabs>
      </BaseModal.Content>
    </BaseModal>
  );
}
