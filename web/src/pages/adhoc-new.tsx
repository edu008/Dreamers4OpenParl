import { useState } from "react"
import { Link } from "react-router"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { useApi } from "@/hooks/use-api"
import { useReview } from "@/hooks/use-review"
import {
  createAdhoc,
  HttpError,
  previewAdhoc,
  suggestKeywords,
  termCount,
  toTerms,
  type AdhocCreated,
  type AdhocPreview,
  type Keywords,
} from "@/lib/adhoc"
import { formatHours, type RunsSummary } from "@/lib/runs"

const number = new Intl.NumberFormat("de-CH")

/** Ab so vielen Stunden Laufzeit warnt die Vorschau: zu breit für einen sinnvollen Lauf. */
const LONG_RUN_HOURS = 3

const TEXTAREA =
  "min-h-20 w-full rounded-md border border-input bg-transparent px-2.5 py-2 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"

const LANGUAGES: { key: keyof Keywords; label: string }[] = [
  { key: "de", label: "Deutsch" },
  { key: "fr", label: "Französisch" },
  { key: "it", label: "Italienisch" },
]

type Texts = Record<keyof Keywords, string>

function keywordsOf(texts: Texts): Keywords {
  return {
    de: toTerms(texts.de),
    fr: toTerms(texts.fr),
    it: toTerms(texts.it),
  }
}

/** Die API verlangt eine Beschreibung; ohne eigene Angabe genügt der Name des Themas. */
function descriptionFor(title: string, own: string): string {
  const text = own.trim()
  return text.length >= 10 ? text : `Geschäfte zum Thema «${title.trim()}».`
}

// Ad-hoc-Thema anlegen in zwei Schritten: Thema nennen, dann Treffer ansehen und anlegen. Die
// Stichwörter schlägt das Sprachmodell im Hintergrund vor; wer will, passt sie an (eingeklappt).
// Angelegt wird erst auf den Knopf eines Menschen; danach prüft Apertus die Kandidaten, und die
// Treffer erscheinen als vorläufig auf der Themenseite.
export function AdhocNewPage() {
  const { name } = useReview()
  const runs = useApi<RunsSummary>("/v1/jobs/summary")
  // Gemessenes Tempo des letzten Laufs, für die Schätzung der Dauer.
  const tempo = runs.data?.runs.find((run) => (run.per_minute ?? 0) > 0)?.per_minute
  const [title, setTitle] = useState("")
  const [description, setDescription] = useState("")
  const [texts, setTexts] = useState<Texts | null>(null)
  const [since, setSince] = useState("")
  const [preview, setPreview] = useState<AdhocPreview>()
  const [busy, setBusy] = useState<"preview" | "create" | null>(null)
  const [error, setError] = useState<string>()
  const [created, setCreated] = useState<AdhocCreated>()

  const titleOk = title.trim().length >= 2
  const keywords = texts ? keywordsOf(texts) : null

  function fail(failure: unknown) {
    if (failure instanceof HttpError && failure.status === 409) {
      setError(`Dieses Thema gibt es schon: ${failure.message}`)
    } else if (failure instanceof HttpError && failure.status === 503) {
      setError(
        `Das Sprachmodell oder die Datenbank ist gerade nicht erreichbar. ${failure.message}`
      )
    } else {
      setError(failure instanceof Error ? failure.message : String(failure))
    }
  }

  /** Schritt 1: Stichwörter vorschlagen lassen und gleich die Treffer zählen. */
  async function start() {
    setBusy("preview")
    setError(undefined)
    setPreview(undefined)
    try {
      const suggested = await suggestKeywords(
        title.trim(),
        descriptionFor(title, description)
      )
      setTexts({
        de: suggested.de.join("\n"),
        fr: suggested.fr.join("\n"),
        it: suggested.it.join("\n"),
      })
      setPreview(
        await previewAdhoc({ keywords: suggested, since: since || null })
      )
    } catch (failure) {
      fail(failure)
    } finally {
      setBusy(null)
    }
  }

  /** Nach angepassten Stichwörtern neu zählen. */
  async function recount() {
    if (!keywords) return
    setBusy("preview")
    setError(undefined)
    try {
      setPreview(await previewAdhoc({ keywords, since: since || null }))
    } catch (failure) {
      fail(failure)
    } finally {
      setBusy(null)
    }
  }

  async function create() {
    if (!keywords) return
    setBusy("create")
    setError(undefined)
    try {
      setCreated(
        await createAdhoc({
          name_de: title.trim(),
          description_de: descriptionFor(title, description),
          keywords,
          since: since || null,
          broader: [],
          user_name: name.trim() || "Admin",
        })
      )
    } catch (failure) {
      fail(failure)
    } finally {
      setBusy(null)
    }
  }

  if (created) {
    return (
      <div className="flex max-w-[68ch] flex-col gap-4">
        <h1 className="font-heading text-2xl leading-tight font-semibold">
          Thema angelegt
        </h1>
        <Alert>
          <AlertTitle>«{title.trim()}» wird jetzt ausgewertet</AlertTitle>
          <AlertDescription>
            {number.format(created.jobs)} Geschäfte werden mit dem Sprachmodell
            geprüft ({number.format(created.candidates)} aus der Stichwortsuche,{" "}
            {number.format(created.sample)} zur Kontrolle). Die Treffer
            erscheinen nach und nach auf der Themenseite, zuerst als
            vorläufig.
          </AlertDescription>
        </Alert>
        <p className="flex flex-wrap gap-x-4 text-sm">
          <Link
            to={`/admin/themen/${created.tag_id}`}
            className="py-2 underline underline-offset-2"
          >
            Zur Themenseite
          </Link>
          <Link to="/admin" className="py-2 underline underline-offset-2">
            Verarbeitungsstand
          </Link>
        </p>
      </div>
    )
  }

  const candidates = preview?.candidates ?? 0
  const checks = candidates + (preview?.sample ?? 0)
  const hours = tempo ? checks / tempo / 60 : null
  const broad = hours !== null && hours > LONG_RUN_HOURS

  return (
    <div className="flex max-w-[68ch] flex-col gap-6">
      <div className="flex flex-col gap-2">
        <h1 className="font-heading text-2xl leading-tight font-semibold text-balance">
          Neues Thema
        </h1>
        <p className="text-sm text-muted-foreground">
          Nenne ein Thema, zum Beispiel «Covid-19». Das System sucht passende
          Geschäfte im ganzen Bestand und lässt sie vom Sprachmodell prüfen,
          ohne Training.
        </p>
      </div>

      <section aria-label="Thema nennen" className="flex flex-col gap-3">
        <label className="flex flex-col gap-1 text-xs text-muted-foreground">
          Thema
          <Input
            value={title}
            maxLength={120}
            placeholder="z. B. Covid-19"
            onChange={(event) => {
              setTitle(event.target.value)
              setTexts(null)
              setPreview(undefined)
            }}
            onKeyDown={(event) => {
              if (event.key === "Enter" && titleOk && busy === null) start()
            }}
          />
        </label>
        <details className="text-xs text-muted-foreground">
          <summary className="cursor-pointer py-1 underline-offset-2 hover:underline">
            Genauer beschreiben (optional)
          </summary>
          <label className="mt-2 flex flex-col gap-1">
            Was gehört dazu, was nicht? Das verbessert die Treffer.
            <textarea
              className={TEXTAREA}
              value={description}
              maxLength={2000}
              onChange={(event) => {
                setDescription(event.target.value)
                setTexts(null)
                setPreview(undefined)
              }}
            />
          </label>
        </details>
        <div>
          <Button disabled={!titleOk || busy !== null} onClick={start}>
            {busy === "preview" && !texts
              ? "Treffer werden gesucht …"
              : "Treffer ansehen"}
          </Button>
        </div>
      </section>

      {preview && keywords && texts && (
        <section aria-label="Treffer" className="flex flex-col gap-3">
          <div role="status" className="flex flex-col gap-2">
            <p className="text-sm">
              <span className="tabular text-2xl font-semibold">
                {number.format(candidates)}
              </span>{" "}
              Geschäfte treffen die Stichwörter
              {preview.sample > 0 && (
                <span className="text-muted-foreground">
                  , dazu {number.format(preview.sample)} zur Kontrolle
                </span>
              )}
              .
            </p>
            {preview.examples.length > 0 && (
              <ul className="flex flex-col gap-1 text-xs text-muted-foreground">
                {preview.examples.map((example) => (
                  <li key={example.affair_id}>
                    {[example.number, example.body_name]
                      .filter(Boolean)
                      .join(" · ")}
                    {": "}
                    <Link
                      to={`/geschaefte/${example.affair_id}`}
                      className="text-foreground underline underline-offset-2"
                    >
                      {example.title ?? `Geschäft ${example.affair_id}`}
                    </Link>
                  </li>
                ))}
              </ul>
            )}
            {hours !== null && candidates > 0 && (
              <p
                className={
                  broad
                    ? "text-xs text-level-medium"
                    : "text-xs text-muted-foreground"
                }
              >
                Das sind {number.format(checks)} Prüfungen mit dem Sprachmodell,
                bei dem aktuellen Tempo {formatHours(hours)}.
                {broad &&
                  " Mit engeren Stichwörtern oder einem Datum wird der Lauf kleiner."}
              </p>
            )}
            {candidates === 0 && (
              <p className="text-xs text-muted-foreground">
                Keine Treffer: Die Stichwörter sind wohl zu eng. Passe sie an.
              </p>
            )}
          </div>

          <details className="text-xs text-muted-foreground">
            <summary className="cursor-pointer py-1 underline-offset-2 hover:underline">
              Stichwörter anpassen ({termCount(keywords)})
            </summary>
            <div className="mt-2 flex flex-col gap-3">
              <p>
                Ein Stichwort pro Zeile, Mehrwortbegriffe gelten als Phrase.
              </p>
              <div className="grid gap-3 sm:grid-cols-3">
                {LANGUAGES.map((language) => (
                  <label key={language.key} className="flex flex-col gap-1">
                    {language.label}
                    <textarea
                      className={TEXTAREA}
                      value={texts[language.key]}
                      onChange={(event) =>
                        setTexts({ ...texts, [language.key]: event.target.value })
                      }
                    />
                  </label>
                ))}
              </div>
              <label className="flex max-w-xs flex-col gap-1">
                Nur Geschäfte ab Datum (optional)
                <Input
                  type="date"
                  value={since}
                  onChange={(event) => setSince(event.target.value)}
                />
              </label>
              <div>
                <Button
                  size="sm"
                  variant="outline"
                  disabled={termCount(keywords) === 0 || busy !== null}
                  onClick={recount}
                >
                  {busy === "preview" ? "Wird gezählt …" : "Neu zählen"}
                </Button>
              </div>
            </div>
          </details>

          <div className="flex flex-col gap-2 border-t border-border pt-4">
            <p className="text-xs text-muted-foreground">
              Das Thema bleibt «vorläufig», bis es jemand freischaltet. Es
              startet Läufe mit dem Sprachmodell.
            </p>
            <div>
              <Button
                disabled={candidates === 0 || busy !== null}
                onClick={create}
              >
                {busy === "create"
                  ? "Thema wird angelegt …"
                  : "Thema anlegen und auswerten"}
              </Button>
            </div>
          </div>
        </section>
      )}

      {error && (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      )}
    </div>
  )
}
