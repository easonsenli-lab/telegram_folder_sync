import { Globe, Landmark, SlidersHorizontal, Clock } from 'lucide-react';
import { siteConfig } from '../data/content';

const icons = [Globe, Landmark, SlidersHorizontal, Clock];

export default function MetricsPanel() {
  return (
    <div className="flex flex-col gap-8 py-4 select-none font-sans max-w-xs">
      {siteConfig.metrics.map((metric, idx) => {
        const Icon = icons[idx];
        return (
          <div key={metric.label} className="group flex items-start gap-4 text-left">
            
            {/* Left: Gold Icon */}
            <div className="w-8 h-8 rounded-lg bg-brand-gold/5 flex items-center justify-center text-brand-gold border border-brand-gold/15 shrink-0 group-hover:scale-110 transition-transform duration-300">
              <Icon className="w-4 h-4" strokeWidth={1.5} />
            </div>

            {/* Right: Text Column */}
            <div className="flex flex-col">
              <span className="text-[9px] uppercase tracking-[0.2em] text-brand-textMuted font-medium mb-0.5">
                {metric.label}
              </span>
              <span className="text-2xl font-light text-gold-gradient tracking-tight leading-none mb-1">
                {metric.value}
              </span>
              <span className="text-[10px] tracking-wide text-brand-textSecondary font-light">
                {metric.subLabel}
              </span>
            </div>

          </div>
        );
      })}
    </div>
  );
}
