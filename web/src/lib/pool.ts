/** Führt die Aufgaben mit höchstens `size` gleichzeitigen Anfragen aus, Ergebnis in Eingabereihenfolge. */
export async function pool<T, R>(
  items: T[],
  size: number,
  work: (item: T) => Promise<R>
): Promise<R[]> {
  const results = new Array<R>(items.length)
  let next = 0
  async function run(): Promise<void> {
    while (next < items.length) {
      const index = next++
      results[index] = await work(items[index])
    }
  }
  await Promise.all(Array.from({ length: Math.min(size, items.length) }, run))
  return results
}
