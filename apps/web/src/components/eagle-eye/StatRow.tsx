type StatRowProps = {
  label: string;
  value: string;
  valueClassName?: string;
  aside?: string;
};

export function StatRow({ label, value, valueClassName = "text-[#EAF4FF]", aside }: StatRowProps) {
  return (
    <div className="flex items-center justify-between gap-3 border-b border-white/8 py-3 last:border-b-0 last:pb-0">
      <span className="text-[13px] text-[#8fa4b8]">{label}</span>
      <div className="flex items-center gap-2">
        <span className={`text-[13px] font-medium ${valueClassName}`}>{value}</span>
        {aside ? <span className="text-[11px] text-[#6f8192]">{aside}</span> : null}
      </div>
    </div>
  );
}
