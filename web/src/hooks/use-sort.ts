import { useState } from "react"

export type SortDir = "asc" | "desc"

// Sortierzustand einer Tabelle. Ein Klick auf dieselbe Spalte dreht die Richtung um, eine neue
// Spalte beginnt mit ihrer eigenen Startrichtung (Zahlen und Daten absteigend, Text aufsteigend).
export function useSort<K extends string>(initialKey: K, initialDir: SortDir) {
  const [key, setKey] = useState<K>(initialKey)
  const [dir, setDir] = useState<SortDir>(initialDir)

  function sortBy(next: K, firstDir: SortDir) {
    if (next === key) {
      setDir(dir === "asc" ? "desc" : "asc")
    } else {
      setKey(next)
      setDir(firstDir)
    }
  }

  return { key, dir, sortBy }
}

export function compareValues(
  left: string | number,
  right: string | number,
  dir: SortDir
): number {
  const factor = dir === "asc" ? 1 : -1
  if (typeof left === "number" && typeof right === "number") {
    return (left - right) * factor
  }
  return String(left).localeCompare(String(right), "de") * factor
}
