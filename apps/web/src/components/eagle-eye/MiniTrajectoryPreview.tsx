export function MiniTrajectoryPreview() {
  return (
    <div className="relative overflow-hidden rounded-[8px] border border-white/10 bg-[#07101a]">
      <div className="mini-preview-grid absolute inset-0 opacity-55" />
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_30%,rgba(80,150,220,0.12),transparent_52%),radial-gradient(circle_at_70%_50%,rgba(255,170,77,0.12),transparent_34%)]" />
      <div className="absolute inset-x-0 bottom-0 h-[70%] bg-[radial-gradient(ellipse_at_center_bottom,rgba(115,168,214,0.45),rgba(19,41,62,0.2)_38%,transparent_68%)]" />
      <svg className="absolute inset-0 h-full w-full" viewBox="0 0 280 150" fill="none" aria-hidden="true">
        <path d="M18 104C54 80 108 52 166 34c32-10 65-13 96-10" stroke="rgba(255,170,77,0.9)" strokeWidth="1.7" />
        <path d="M18 112C72 70 118 60 170 70c38 8 64 22 92 46" stroke="rgba(110,255,151,0.8)" strokeWidth="1.4" />
        <circle cx="42" cy="95" r="3" fill="#FFAA4D" />
        <circle cx="144" cy="68" r="3" fill="#6EFF97" />
        <circle cx="246" cy="124" r="3" fill="#58C7FF" />
      </svg>
      <div className="absolute bottom-2 right-2 rounded-full border border-white/10 bg-black/45 px-2 py-1 text-[10px] tracking-[0.18em] text-[#6d8296]">
        24.0 MIN ETA
      </div>
      <div className="relative aspect-[1.72/1]" />
    </div>
  );
}
