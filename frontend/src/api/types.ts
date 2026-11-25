/* Generated from src/api/schema.json by `npm run gen:types`. Do not edit. */

export interface ApiSchema {
  BasketEntry: BasketEntry;
  ConfigFile: ConfigFile;
  Configs: Configs;
  DataProvenance: DataProvenance;
  DeflatedSharpe: DeflatedSharpe;
  EquitySeries: EquitySeries;
  ErrorBody: ErrorBody;
  Gate: Gate;
  Gates: Gates;
  Headline: Headline;
  HeadlineCandidate: HeadlineCandidate;
  Meta: Meta;
  OpenAtEnd: OpenAtEnd;
  PairEntry: PairEntry;
  Pairs: Pairs;
  Period: Period;
  PlaceboRank: PlaceboRank;
  Provenance: Provenance;
  RunCompare: RunCompare;
  RunList: RunList;
  RunListItem: RunListItem;
  RunManifest: RunManifest;
  ScreenCriterion: ScreenCriterion;
  ScreenStatus: ScreenStatus;
  Snapshot: Snapshot;
  SourceInfoModel: SourceInfoModel;
  SpanMetrics: SpanMetrics;
  StudyPeriods: StudyPeriods;
  SummaryRow: SummaryRow;
  SyntheticEntry: SyntheticEntry;
  Table: Table;
  TableFile: TableFile;
  TrialItem: TrialItem;
  TrialPage: TrialPage;
  TrialStats: TrialStats;
}
/**
 * This interface was referenced by `ApiSchema`'s JSON-Schema
 * via the `definition` "BasketEntry".
 */
export interface BasketEntry {
  screen: ScreenStatus;
  tickers: string[];
}
/**
 * Latest formation-period screen result of a ticker set.
 *
 * This interface was referenced by `ApiSchema`'s JSON-Schema
 * via the `definition` "ScreenStatus".
 */
export interface ScreenStatus {
  criteria: ScreenCriterion[];
  reason: string | null;
  status: "pass" | "fail" | "refused" | "error" | "not_analysed";
  trial_id: string | null;
}
/**
 * This interface was referenced by `ApiSchema`'s JSON-Schema
 * via the `definition` "ScreenCriterion".
 */
export interface ScreenCriterion {
  detail: string;
  name: string;
  passed: boolean;
}
/**
 * This interface was referenced by `ApiSchema`'s JSON-Schema
 * via the `definition` "ConfigFile".
 */
export interface ConfigFile {
  name: string;
  path: string;
  sha256: string;
  text: string;
}
/**
 * This interface was referenced by `ApiSchema`'s JSON-Schema
 * via the `definition` "Configs".
 */
export interface Configs {
  configs: ConfigFile[];
}
/**
 * This interface was referenced by `ApiSchema`'s JSON-Schema
 * via the `definition` "DataProvenance".
 */
export interface DataProvenance {
  cached_tickers: string[];
  snapshots: Snapshot[];
  sources: SourceInfoModel[];
}
/**
 * This interface was referenced by `ApiSchema`'s JSON-Schema
 * via the `definition` "Snapshot".
 */
export interface Snapshot {
  downloaded_before_terms_check: boolean | null;
  file_present: boolean;
  first_date: string | null;
  key: string;
  last_date: string | null;
  n_rows: number;
  retrieved_at_utc: string;
  snapshot_id: string;
  source: string;
  url: string;
}
/**
 * This interface was referenced by `ApiSchema`'s JSON-Schema
 * via the `definition` "SourceInfoModel".
 */
export interface SourceInfoModel {
  downloads_enabled: boolean;
  name: string;
  reference: string;
  terms_checked_on: string | null;
  terms_note: string;
  title: string;
}
/**
 * This interface was referenced by `ApiSchema`'s JSON-Schema
 * via the `definition` "DeflatedSharpe".
 */
export interface DeflatedSharpe {
  dsr: number | null;
  expected_max: number | null;
  n_defined: number;
  n_trials: number;
  sharpe_variance: number | null;
}
/**
 * Equity and drawdown of one span, as fractions of the fixed capital.
 *
 * This interface was referenced by `ApiSchema`'s JSON-Schema
 * via the `definition` "EquitySeries".
 */
export interface EquitySeries {
  cost_bps: number | null;
  dates: string[];
  drawdown: (number | null)[];
  end: string;
  equity: (number | null)[];
  gross_equity: (number | null)[];
  provenance: Provenance;
  run_id: string;
  span: string;
  start: string;
  stored_max_drawdown: number | null;
  stored_total_return: number | null;
}
/**
 * Which code, configs and data produced a result.
 *
 * This interface was referenced by `ApiSchema`'s JSON-Schema
 * via the `definition` "Provenance".
 */
export interface Provenance {
  code_commit: string;
  code_dirty: boolean;
  config_hashes: {
    [k: string]: string | undefined;
  };
  snapshot_ids?: {
    [k: string]: string | undefined;
  } | null;
  trial_id?: string | null;
}
/**
 * Every error response: a plain message with the endpoint and run id.
 *
 * This interface was referenced by `ApiSchema`'s JSON-Schema
 * via the `definition` "ErrorBody".
 */
export interface ErrorBody {
  endpoint: string;
  error: string;
  message: string;
  run_id?: string | null;
}
/**
 * This interface was referenced by `ApiSchema`'s JSON-Schema
 * via the `definition` "Gate".
 */
export interface Gate {
  evidence: string[];
  gate: string;
  passed_on: string | null;
  phase: string;
  status: "passed" | "not_started" | "in_progress";
  title: string;
}
/**
 * This interface was referenced by `ApiSchema`'s JSON-Schema
 * via the `definition` "Gates".
 */
export interface Gates {
  gates: Gate[];
}
/**
 * The strategy as stated in advance (backtest.runner, the summary).
 *
 * This interface was referenced by `ApiSchema`'s JSON-Schema
 * via the `definition` "Headline".
 */
export interface Headline {
  candidate_states: {
    [k: string]: number | undefined;
  };
  candidates: HeadlineCandidate[];
  complete: boolean;
  deflated_sharpe: {
    [k: string]: DeflatedSharpe | null | undefined;
  } | null;
  duplicate_run_ids_ignored: string[];
  metrics: {
    [k: string]: SpanMetrics | null | undefined;
  } | null;
  n_candidates: number;
  n_runs: number;
  out_of_sample_span: string;
  run_ids: string[];
  spans_in_sample_for_screen: string[];
  statement: string;
}
/**
 * This interface was referenced by `ApiSchema`'s JSON-Schema
 * via the `definition` "HeadlineCandidate".
 */
export interface HeadlineCandidate {
  reason: string | null;
  run_id: string | null;
  screen_status?: string | null;
  screen_status_at_run?: string | null;
  state: string;
  tickers: string[];
}
/**
 * Metrics of one span, as backtest.summary.span_metrics stores them.
 *
 * This interface was referenced by `ApiSchema`'s JSON-Schema
 * via the `definition` "SpanMetrics".
 */
export interface SpanMetrics {
  annual_turnover: number | null;
  annualised_return: number | null;
  annualised_volatility: number | null;
  average_abs_net_exposure: number | null;
  average_gross_exposure: number | null;
  average_holding_bars: number | null;
  beta_to_benchmark: number | null;
  borrow_cost_return: number | null;
  calmar: number | null;
  cost_drag: number | null;
  distribution_return: number | null;
  end: string;
  exit_reasons: {
    [k: string]: number | undefined;
  };
  gross_sharpe: number | null;
  hit_rate: number | null;
  kurtosis: number | null;
  max_drawdown: number | null;
  n_days: number;
  n_trades: number;
  price_return: number | null;
  psr_zero: number | null;
  share_in_market: number | null;
  sharpe: number | null;
  sharpe_per_period: number | null;
  skewness: number | null;
  sortino: number | null;
  start: string;
  total_return: number | null;
  trade_cost_return: number | null;
}
/**
 * State of the project when the page loads.
 *
 * This interface was referenced by `ApiSchema`'s JSON-Schema
 * via the `definition` "Meta".
 */
export interface Meta {
  data_first_date: string | null;
  data_last_date: string | null;
  downloads_enabled: boolean;
  head_commit: string;
  head_dirty: boolean;
  latest_summary_id: string | null;
  latest_summary_trials_counted: number | null;
  paper_trading_only: boolean;
  project: string;
  study: StudyPeriods;
  summary_stale: boolean;
  trials_counted: number;
  trials_in_log: number;
}
/**
 * This interface was referenced by `ApiSchema`'s JSON-Schema
 * via the `definition` "StudyPeriods".
 */
export interface StudyPeriods {
  formation_end: string;
  formation_start: string;
  test_period_locked: boolean;
  test_start: string;
  validation_end: string;
  validation_start: string;
}
/**
 * This interface was referenced by `ApiSchema`'s JSON-Schema
 * via the `definition` "OpenAtEnd".
 */
export interface OpenAtEnd {
  exit_cost_not_charged_return: number | null;
  open: boolean;
  unrealised_net_pnl_return: number | null;
}
/**
 * This interface was referenced by `ApiSchema`'s JSON-Schema
 * via the `definition` "PairEntry".
 */
export interface PairEntry {
  a: string;
  b: string;
  label: string;
  screen: ScreenStatus;
}
/**
 * This interface was referenced by `ApiSchema`'s JSON-Schema
 * via the `definition` "Pairs".
 */
export interface Pairs {
  basket: BasketEntry;
  pairs: PairEntry[];
  synthetic: SyntheticEntry;
}
/**
 * This interface was referenced by `ApiSchema`'s JSON-Schema
 * via the `definition` "SyntheticEntry".
 */
export interface SyntheticEntry {
  a: string;
  b: string;
  beta: number;
  half_life: number;
  label: string;
  screen: ScreenStatus;
  seed: number;
}
/**
 * This interface was referenced by `ApiSchema`'s JSON-Schema
 * via the `definition` "Period".
 */
export interface Period {
  asof: string;
  name: string;
  start: string;
}
/**
 * This interface was referenced by `ApiSchema`'s JSON-Schema
 * via the `definition` "PlaceboRank".
 */
export interface PlaceboRank {
  n_placebos: number | null;
  placebo_mean: number | null;
  real_sharpe: number | null;
  share_at_least: number | null;
}
/**
 * This interface was referenced by `ApiSchema`'s JSON-Schema
 * via the `definition` "RunCompare".
 */
export interface RunCompare {
  a: RunManifest;
  b: RunManifest;
}
/**
 * run.json of a backtest, control batch or summary.
 *
 * Fields that a kind does not have are null. A test checks that every key
 * the runner writes is a field here, so nothing is dropped silently.
 *
 * This interface was referenced by `ApiSchema`'s JSON-Schema
 * via the `definition` "RunManifest".
 */
export interface RunManifest {
  control?: string | null;
  cost_bps?: number | null;
  created_at_utc: string;
  data_source?: string | null;
  default_cost_bps?: number | null;
  default_hedge?: string | null;
  deflated_sharpe?: {
    [k: string]: DeflatedSharpe | null | undefined;
  } | null;
  downloaded?: string[] | null;
  exploratory_screened_run_ids?: string[] | null;
  files: {
    [k: string]: TableFile | undefined;
  };
  first_signal_date?: string | null;
  flags?:
    | {
        [k: string]: unknown | undefined;
      }[]
    | null;
  headline?: Headline | null;
  hedge?: string | null;
  kind: "backtest" | "control_batch" | "summary";
  label?: string | null;
  metrics?: {
    [k: string]: SpanMetrics | null | undefined;
  } | null;
  n_backtests_counted?: number | null;
  n_trials_counted?: number | null;
  n_trials_in_log?: number | null;
  n_windows?: number | null;
  open_at_end?: OpenAtEnd | null;
  out_of_sample_span?: string | null;
  period?: Period | null;
  provenance: Provenance;
  rank?: {
    [k: string]: PlaceboRank | undefined;
  } | null;
  real_run_id?: string | null;
  real_sharpe?: number | null;
  rows?: SummaryRow[] | null;
  run_id: string;
  schema_version: number;
  screen?: ScreenStatus | null;
  screened_not_backtested?: string[][] | null;
  settings?: {
    [k: string]: unknown | undefined;
  } | null;
  spans_in_sample_for_screen?: string[] | null;
  stale?: boolean;
  strategy?: string | null;
  summary?: {
    [k: string]: unknown | undefined;
  } | null;
  survivorship_bias?: boolean | null;
  tickers?: string[] | null;
  unlisted_case_study_run_ids?: string[] | null;
}
/**
 * This interface was referenced by `ApiSchema`'s JSON-Schema
 * via the `definition` "TableFile".
 */
export interface TableFile {
  columns: string[];
  file: string;
  rows: number;
  sha256: string;
}
/**
 * This interface was referenced by `ApiSchema`'s JSON-Schema
 * via the `definition` "SummaryRow".
 */
export interface SummaryRow {
  cost_bps: number;
  data_source: string;
  deflated_sharpe: {
    [k: string]: DeflatedSharpe | null | undefined;
  } | null;
  hedge: string;
  label: string;
  metrics: {
    [k: string]: SpanMetrics | null | undefined;
  };
  open_at_end: OpenAtEnd | null;
  run_id: string;
  screen_status: string | null;
  screen_status_at_run: string | null;
  strategy: string;
  tickers: string[];
}
/**
 * This interface was referenced by `ApiSchema`'s JSON-Schema
 * via the `definition` "RunList".
 */
export interface RunList {
  runs: RunListItem[];
}
/**
 * This interface was referenced by `ApiSchema`'s JSON-Schema
 * via the `definition` "RunListItem".
 */
export interface RunListItem {
  code_commit: string | null;
  code_dirty: boolean | null;
  control: string | null;
  cost_bps: number | null;
  created_at_utc: string | null;
  data_source: string | null;
  hedge: string | null;
  kind: string;
  label: string | null;
  run_id: string;
  stale: boolean;
  strategy: string | null;
  tickers: string[] | null;
}
/**
 * One stored table as columns. Dates are ISO strings; NaN is null.
 *
 * This interface was referenced by `ApiSchema`'s JSON-Schema
 * via the `definition` "Table".
 */
export interface Table {
  columns: {
    [k: string]: (number | string | boolean | null)[] | undefined;
  };
  index: (string | number)[];
  index_name: string | null;
  name: string;
  run_id: string;
  sha256: string;
}
/**
 * One line of the trial log, with its 1-based line number.
 *
 * This interface was referenced by `ApiSchema`'s JSON-Schema
 * via the `definition` "TrialItem".
 */
export interface TrialItem {
  code_commit: string;
  code_dirty: boolean;
  config_hashes: {
    [k: string]: string | undefined;
  };
  counted: boolean;
  data_source: string;
  kind: string;
  label: string | null;
  line: number;
  outcome: string;
  parameters: {
    [k: string]: unknown | undefined;
  };
  period: {
    [k: string]: unknown | undefined;
  };
  reason: string | null;
  recorded_at_utc: string;
  results: {
    [k: string]: unknown | undefined;
  };
  schema_version: number;
  snapshot_ids: {
    [k: string]: string | undefined;
  };
  survivorship_bias: boolean;
  test_period_touched: boolean;
  tickers: string[];
  trial_id: string;
  unlock: {
    [k: string]: string | undefined;
  } | null;
}
/**
 * This interface was referenced by `ApiSchema`'s JSON-Schema
 * via the `definition` "TrialPage".
 */
export interface TrialPage {
  items: TrialItem[];
  limit: number;
  offset: number;
  total: number;
}
/**
 * This interface was referenced by `ApiSchema`'s JSON-Schema
 * via the `definition` "TrialStats".
 */
export interface TrialStats {
  by_kind: {
    [k: string]: number | undefined;
  };
  by_label: {
    [k: string]: number | undefined;
  };
  by_outcome: {
    [k: string]: number | undefined;
  };
  counting_rule: string;
  dirty_lines: number[];
  n_backtests_counted: number;
  n_counted: number;
  n_lines: number;
  n_screened_not_backtested: number;
}
