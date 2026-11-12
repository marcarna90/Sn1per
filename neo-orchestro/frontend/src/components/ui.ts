/** Shared Tailwind class strings, so the design stays consistent and accessible. */
export const ui = {
  h1: "text-2xl font-semibold tracking-tight text-slate-900 dark:text-slate-50",
  h2: "text-lg font-semibold text-slate-900 dark:text-slate-50",
  card: "rounded-lg border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-700 dark:bg-slate-800",
  label: "block text-sm font-medium text-slate-800 dark:text-slate-200",
  hint: "text-sm text-slate-600 dark:text-slate-400",
  input:
    "mt-1 block w-full rounded-md border border-slate-400 bg-white px-3 py-2 text-slate-900 " +
    "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-700 " +
    "dark:border-slate-500 dark:bg-slate-900 dark:text-slate-100",
  button:
    "inline-flex items-center justify-center rounded-md bg-indigo-700 px-4 py-2 text-sm font-medium " +
    "text-white hover:bg-indigo-800 focus-visible:outline-2 focus-visible:outline-offset-2 " +
    "focus-visible:outline-indigo-700 disabled:cursor-not-allowed disabled:opacity-60",
  buttonSecondary:
    "inline-flex items-center justify-center rounded-md border border-slate-400 bg-white px-3 py-1.5 " +
    "text-sm font-medium text-slate-900 hover:bg-slate-100 focus-visible:outline-2 " +
    "focus-visible:outline-offset-2 focus-visible:outline-indigo-700 disabled:cursor-not-allowed " +
    "disabled:opacity-60 dark:border-slate-500 dark:bg-slate-800 dark:text-slate-100 dark:hover:bg-slate-700",
  buttonDanger:
    "inline-flex items-center justify-center rounded-md border border-red-700 bg-white px-3 py-1.5 " +
    "text-sm font-medium text-red-800 hover:bg-red-50 focus-visible:outline-2 " +
    "focus-visible:outline-offset-2 focus-visible:outline-red-700 dark:bg-slate-800 dark:text-red-300",
  link: "text-indigo-700 underline underline-offset-2 hover:text-indigo-900 dark:text-indigo-300",
  tableWrap: "overflow-x-auto rounded-lg border border-slate-200 dark:border-slate-700",
  table: "min-w-full divide-y divide-slate-200 text-left text-sm dark:divide-slate-700",
  th: "px-3 py-2 font-semibold text-slate-800 dark:text-slate-200",
  td: "px-3 py-2 align-top text-slate-800 dark:text-slate-200",
} as const;
