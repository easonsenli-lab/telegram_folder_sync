import { useState, useEffect } from 'react';
import { siteConfig } from '../data/content';
import { X } from 'lucide-react';

export default function Header() {
  const [isScrolled, setIsScrolled] = useState(false);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  useEffect(() => {
    const handleScroll = () => {
      if (window.scrollY > 20) {
        setIsScrolled(true);
      } else {
        setIsScrolled(false);
      }
    };
    window.addEventListener('scroll', handleScroll);
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  return (
    <header
      className={`fixed top-0 left-0 w-full z-50 transition-all duration-500 py-5 ${
        isScrolled
          ? 'bg-brand-dark/80 backdrop-blur-md border-b border-white/5'
          : 'bg-transparent border-b border-transparent'
      }`}
    >
      <div className="max-w-[1400px] mx-auto px-6 md:px-12 flex items-center justify-between">
        
        {/* Left: Logo (Circle Rose + Text) */}
        <a href="#top" className="flex items-center gap-3 group" aria-label="RosePay Home">
          <img src="/rosepay-mark.png" alt="" className="w-8 h-8 shrink-0 drop-shadow-[0_0_12px_rgba(217,164,65,0.35)]" />
          <span className="text-xl font-light tracking-[0.15em] text-brand-textPrimary font-serif">
            Rose<span className="text-brand-gold font-normal">Pay</span>
          </span>
        </a>

        {/* Center: Navigation Links (Capitalized) */}
        <nav className="hidden md:flex items-center gap-8 lg:gap-12">
          {siteConfig.navItems.map((item) => (
            <a
              key={item.label}
              href={item.href}
              className="text-[11px] font-light tracking-[0.18em] text-brand-textSecondary hover:text-brand-gold transition-colors duration-300 font-sans"
            >
              {item.label}
            </a>
          ))}
        </nav>

        {/* Right: CTA & Round Menu Icon */}
        <div className="flex items-center gap-4">
          <a
            href="#about"
            className="hidden sm:inline-flex items-center justify-center px-6 py-2.5 rounded-full text-[10px] font-light tracking-widest text-brand-textPrimary border border-white/20 hover:border-brand-gold hover:text-brand-gold bg-transparent transition-all duration-300 font-sans"
          >
            {siteConfig.ctaText.toUpperCase()}
          </a>

          {/* Circular menu button */}
          <button
            type="button"
            onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
            className="md:hidden w-9 h-9 rounded-full border border-white/25 flex items-center justify-center text-brand-textSecondary hover:text-brand-gold hover:border-brand-gold focus:outline-none transition-all"
            aria-expanded={isMobileMenuOpen}
            aria-label="Toggle navigation menu"
          >
            {isMobileMenuOpen ? (
              <X className="w-4 h-4" />
            ) : (
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-4 h-4">
                <path d="M4 7h16M4 12h16M4 17h16" strokeLinecap="round" />
              </svg>
            )}
          </button>
        </div>
      </div>

      {/* Mobile Dropdown Navigation Menu */}
      <div
        className={`md:hidden absolute top-full left-0 w-full bg-brand-dark/95 border-b border-brand-gold/10 shadow-2xl transition-all duration-300 overflow-hidden ${
          isMobileMenuOpen ? 'max-h-[350px] opacity-100 py-6' : 'max-h-0 opacity-0 pointer-events-none'
        }`}
      >
        <div className="px-8 flex flex-col gap-5">
          {siteConfig.navItems.map((item) => (
            <a
              key={item.label}
              href={item.href}
              onClick={() => setIsMobileMenuOpen(false)}
              className="text-sm font-light tracking-widest text-brand-textSecondary hover:text-brand-gold transition-colors py-2 border-b border-white/5"
            >
              {item.label}
            </a>
          ))}
          <a
            href="#about"
            onClick={() => setIsMobileMenuOpen(false)}
            className="w-full text-center py-3 mt-2 rounded-full text-xs font-bold text-brand-dark bg-gradient-to-r from-brand-gold to-brand-goldLight"
          >
            {siteConfig.ctaText}
          </a>
        </div>
      </div>
    </header>
  );
}
