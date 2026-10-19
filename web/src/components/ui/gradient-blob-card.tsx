import type { ReactNode } from "react"
import { cn } from "cn"

// Nach der Vorlage «GradientBlobCard»: ein verglastes Feld, dahinter wandert ein Farbfleck.
// Angepasst an DESIGN.md: Schweizer Rot statt Pink-Gelb, eckig, Bewegung nur mit motion-safe.
export function GradientBlobCard({
  children,
  className,
}: {
  children: ReactNode
  className?: string
}) {
  return (
    <div
      className={cn(
        "relative overflow-hidden shadow-[20px_20px_60px_rgb(0_0_0/0.25)]",
        className
      )}
    >
      <div
        aria-hidden
        className="absolute top-1/2 left-1/2 z-0 aspect-square w-[70%] bg-gradient-to-r from-primary via-[#ff4d42] to-[#ff8a65] blur-[40px] motion-safe:animate-blob"
      />
      <div
        aria-hidden
        className="absolute inset-[5px] z-10 bg-background/95 outline-2 outline-background backdrop-blur-[24px]"
      />
      {/* Der Inhalt liegt auf dem Glas; nur der 5-px-Rand zeigt den Fleck. */}
      <div className="relative z-20 p-[5px]">{children}</div>
    </div>
  )
}
