import { ArrowDown, ArrowUp, ArrowUpDown } from "lucide-react";
import { useMemo, useState, type ReactNode } from "react";
import { cx } from "../lib/cx";

export interface Column<Row> {
  key: string;
  label: string;
  align?: "left" | "right";
  /** Sort value; null sorts last. Omit to make the column unsortable. */
  sortValue?: (row: Row) => number | string | null;
  render: (row: Row) => ReactNode;
  width?: string;
}

interface MetricTableProps<Row> {
  columns: Column<Row>[];
  rows: Row[];
  rowKey: (row: Row) => string;
  caption: string;
  initialSort?: { key: string; direction: "asc" | "desc" };
  onRowClick?: (row: Row) => void;
  dense?: boolean;
}

/** Right-aligned tabular numbers, sortable headers, a caption for screen readers. */
export function MetricTable<Row>({ columns, rows, rowKey, caption, initialSort, onRowClick, dense }: MetricTableProps<Row>) {
  const [sort, setSort] = useState(initialSort ?? null);
  const sorted = useMemo(() => {
    const column = columns.find((c) => c.key === sort?.key);
    if (!sort || !column?.sortValue) return rows;
    const get = column.sortValue;
    return [...rows].sort((a, b) => {
      const x = get(a);
      const y = get(b);
      if (x === null && y === null) return 0;
      if (x === null) return 1;
      if (y === null) return -1;
      const order = x < y ? -1 : x > y ? 1 : 0;
      return sort.direction === "asc" ? order : -order;
    });
  }, [rows, columns, sort]);

  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse">
        <caption className="sr-only">{caption}</caption>
        <thead>
          <tr className="border-b border-line">
            {columns.map((column) => {
              const active = sort?.key === column.key;
              const ariaSort = active ? (sort.direction === "asc" ? "ascending" : "descending") : "none";
              const Icon = !active ? ArrowUpDown : sort.direction === "asc" ? ArrowUp : ArrowDown;
              const right = column.align === "right";
              return (
                <th key={column.key} scope="col" aria-sort={column.sortValue ? ariaSort : undefined} style={{ width: column.width }} className={cx("t-label px-3 py-2.5 font-medium text-ink-3", right ? "text-right" : "text-left")}>
                  {column.sortValue ? (
                    <button
                      type="button"
                      onClick={() => setSort({ key: column.key, direction: active && sort.direction === "desc" ? "asc" : "desc" })}
                      className={cx("inline-flex items-center gap-1 uppercase hover:text-ink-2", right && "flex-row-reverse", active && "text-ink-2")}
                    >
                      {column.label}
                      <Icon aria-hidden size={12} className={active ? "opacity-100" : "opacity-40"} />
                    </button>
                  ) : (
                    column.label
                  )}
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {sorted.map((row) => (
            <tr
              key={rowKey(row)}
              onClick={onRowClick ? () => onRowClick(row) : undefined}
              className={cx("border-b border-line/60 transition-colors duration-150 last:border-b-0 hover:bg-glass-hover", onRowClick && "cursor-pointer")}
            >
              {columns.map((column) => (
                <td key={column.key} className={cx("px-3", dense ? "py-1.5" : "py-2.5", column.align === "right" ? "t-num text-right text-ink" : "t-body text-ink")}>
                  {column.render(row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
