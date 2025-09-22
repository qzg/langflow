import type { ColDef } from "ag-grid-community";
import { useMemo, useState } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import TableComponent from "@/components/core/parameterRenderComponent/components/tableComponent";
import { Button } from "@/components/ui/button";
import Loading from "@/components/ui/loading";
import {
  type KnowledgeBaseDocumentsResponse,
  useGetKnowledgeBaseDocuments,
} from "@/controllers/API/queries/knowledge-bases/use-get-knowledge-base-documents";
import type { KnowledgeBaseInfo } from "@/controllers/API/queries/knowledge-bases/use-get-knowledge-bases";
import BaseModal from "@/modals/baseModal";

interface KnowledgeBaseContentModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  knowledgeBase: KnowledgeBaseInfo | null;
}

const baseCellClass =
  "text-muted-foreground select-text align-top whitespace-pre-wrap";

export default function KnowledgeBaseContentModal({
  open,
  onOpenChange,
  knowledgeBase,
}: KnowledgeBaseContentModalProps) {
  const [viewMode, setViewMode] = useState<"table" | "document">("table");

  const { data, isLoading, error } = useGetKnowledgeBaseDocuments(
    knowledgeBase
      ? { kb_name: knowledgeBase.id, limit: 50, offset: 0 }
      : (undefined as any),
    { enabled: Boolean(knowledgeBase?.id) },
  );

  const rows = useMemo(() => {
    if (!data?.items) return [];
    return data.items.map((d) => ({
      id: d.id,
      document: d.document,
      snippet: (d.document || "").slice(0, 500),
      source:
        (d.metadata &&
          (d.metadata.source || d.metadata.file || d.metadata.path)) ||
        "",
      metadata: d.metadata || {},
    }));
  }, [data]);

  const columns: ColDef[] = useMemo(
    () => [
      {
        headerName: "ID",
        field: "id",
        flex: 2,
        sortable: false,
        cellClass: baseCellClass,
      },
      {
        headerName: "Text",
        field: "snippet",
        flex: 6,
        sortable: false,
        cellClass: baseCellClass,
        tooltipValueGetter: (params) => params.data.document,
      },
      {
        headerName: "Source",
        field: "source",
        flex: 2,
        sortable: false,
        cellClass: baseCellClass,
      },
    ],
    [],
  );

  const renderContent = () => {
    if (isLoading) {
      return (
        <div className="flex h-full w-full items-center justify-center">
          <Loading />
        </div>
      );
    }

    if (error) {
      return (
        <div className="p-4 text-sm text-destructive">
          Failed to load knowledge base contents.
        </div>
      );
    }

    if (!rows.length) {
      return (
        <div className="p-4 text-sm text-muted-foreground">
          No documents found in this knowledge base.
        </div>
      );
    }

    if (viewMode === "table") {
      return (
        <div className="flex h-full min-h-[50vh] flex-col">
          <div className="h-full min-h-[50vh]">
            <TableComponent
              rowHeight={52}
              headerHeight={44}
              cellSelection={false}
              pagination
              columnDefs={columns}
              rowData={rows}
              className="ag-no-border ag-knowledge-docs-table h-full w-full"
            />
          </div>
        </div>
      );
    }

    return (
      <div className="grid max-h-[70vh] grid-cols-1 gap-4 overflow-auto p-2 md:grid-cols-2">
        {rows.map((r) => (
          <div key={r.id} className="rounded-md border p-3">
            <div className="mb-1 text-xs text-muted-foreground">{r.source}</div>
            <div className="mb-2 text-[10px] text-muted-foreground">{r.id}</div>
            <div className="whitespace-pre-wrap text-sm">{r.snippet}</div>
          </div>
        ))}
      </div>
    );
  };

  return (
    <BaseModal open={open} setOpen={onOpenChange} size="large">
      <BaseModal.Header description={knowledgeBase?.name || ""}>
        <span className="pr-2">Knowledge Base Contents</span>
        <ForwardedIconComponent name="BookOpenText" className="mr-2 h-4 w-4" />
      </BaseModal.Header>
      <BaseModal.Content>
        <div className="flex h-full flex-col gap-3">
          <div className="flex items-center justify-between gap-2">
            <div className="text-sm font-medium">{knowledgeBase?.name}</div>
            <div className="flex items-center gap-2">
              <Button
                variant={viewMode === "table" ? "default" : "outline"}
                size="sm"
                onClick={() => setViewMode("table")}
              >
                <ForwardedIconComponent name="Table" className="mr-1 h-4 w-4" />
                Table
              </Button>
              <Button
                variant={viewMode === "document" ? "default" : "outline"}
                size="sm"
                onClick={() => setViewMode("document")}
              >
                <ForwardedIconComponent
                  name="FileText"
                  className="mr-1 h-4 w-4"
                />
                Document
              </Button>
            </div>
          </div>
          <div className="flex-1 overflow-hidden">{renderContent()}</div>
        </div>
      </BaseModal.Content>
    </BaseModal>
  );
}
