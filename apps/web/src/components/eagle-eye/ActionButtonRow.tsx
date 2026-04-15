type ActionButton = {
  label: string;
  primary?: boolean;
  onClick?: () => void;
  disabled?: boolean;
};

export function ActionButtonRow({ buttons }: { buttons: ActionButton[] }) {
  return (
    <div className="flex gap-2">
      {buttons.map((button) => (
        <button
          key={button.label}
          onClick={button.onClick}
          disabled={button.disabled}
          className={
            button.primary
              ? `flex-1 rounded-[6px] border px-3 py-2 text-[13px] font-medium transition ${
                  button.disabled
                    ? "cursor-not-allowed border-white/10 bg-white/[0.03] text-[#7f92a6]"
                    : "border-[#9fdcc2]/20 bg-[linear-gradient(180deg,rgba(132,174,151,0.28),rgba(73,100,91,0.28))] text-[#EAF4FF] shadow-[inset_0_0_14px_rgba(110,255,151,0.08)] hover:bg-[linear-gradient(180deg,rgba(132,174,151,0.35),rgba(73,100,91,0.35))]"
                }`
              : `rounded-[6px] border px-3 py-2 text-[13px] transition ${
                  button.disabled
                    ? "cursor-not-allowed border-white/8 bg-white/[0.02] text-[#708293]"
                    : "border-white/10 bg-white/[0.03] text-[#d7e5f2] hover:border-[#58C7FF]/25 hover:bg-[#58C7FF]/[0.06]"
                }`
          }
        >
          {button.label}
        </button>
      ))}
    </div>
  );
}
