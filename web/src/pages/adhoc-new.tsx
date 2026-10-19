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
import type { PageTree } from "@/lib/api"

/** Ab dieser Zahl Prüfungen warnt die Vorschau. */
const LARGE_RUN = 1000

const TEXTAREA =
  "min-h-24 w-full rounded-md border border-input bg-transparent px-2.5 py-2 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"

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

function messageOf(error: unknown): string {
  return error instanceof Error ? error.message : String(error)
}

// Ad-hoc-Thema anlegen: beschreiben, Stichwörter prüfen, Treffer abschätzen, anlegen. Das Modell
// schlägt nur vor, angelegt wird erst auf den Knopf eines Menschen. Danach prüft Apertus die
// Kandidaten und eine Stichprobe; die Treffer erscheinen als vorläufig auf der Themenseite.
export function AdhocNewPage() {
  const { name } = useReview()
  const tree = useApi<PageTree>("/v1/pages")
  const [title, setTitle] = useState("")
  const [description, setDescription] = useState("")
  const [texts, setTexts] = useState<Texts>({ de: "", fr: "", it: "" })
  const [since, setSince] = useState("")
  const [broader, setBroader] = useState("")
  const [busy, setBusy] = useState<"keywords" | "preview" | "create" | null>(
    null
  )
  const [error, setError] = useState<string>()
  const [preview, setPreview] = useState<AdhocPreview>()
  const [created, setCreated] = useState<AdhocCreated>()

  const keywords = keywordsOf(texts)
  const terms = termCount(keywords)
  const nameOk = title.trim().length >= 2
  const descriptionOk = description.trim().length >= 10
  const chapters = (tree.data?.pages ?? []).filter(
    (page) => page.kind === "kapitel"
  )
  const scope = { keywords, since: since || null }

  async function run<T>(
    kind: "keywords" | "preview" | "create",
    action: () => Promise<T>,
    done: (result: T) => void
  ) {
    setBusy(kind)
    setError(undefined)
    try {
      done(await action())
    } catch (failure) {
      if (failure instanceof HttpError && failure.status === 409) {
        setError(`Dieses Thema gibt es schon: ${failure.message}`)
      } else if (failure instanceof HttpError && failure.status === 503) {
        setError(
          `Das Sprachmodell oder die Datenbank ist gerade nicht erreichbar. ${failure.message}`
        )
      } else {
        setError(messageOf(failure))
      }
    } finally {
      setBusy(null)
    }
  }

  const suggest = () =>
    run(
      "keywords",
      () => suggestKeywords(title.trim(), description.trim()),
      (result) => {
        setTexts({
          de: result.de.join("\n"),
          fr: result.fr.join("\n"),
          it: result.it.join("\n"),
        })
        setPreview(undefined)
      }
    )

  const estimate = () =>
    run("preview", () => previewAdhoc(scope), setPreview)

  const create = () =>
    run(
      "create",
      () =>
        createAdhoc({
          name_de: title.trim(),
          description_de: description.trim(),
          ...scope,
          broader: broader ? [broader] : [],
          user_name: name.trim() || "Admin",
        }),
      setCreated
    )

  if (created) {
    return (
      <div className="flex flex-col gap-4">
        <h1 className="font-heading text-2xl leading-tight font-semibold">
          Thema angelegt
        </h1>
        <Alert>
          <AlertTitle>«{title.trim()}» wird jetzt ausgewertet</AlertTitle>
          <AlertDescription>
            {created.jobs} Geschäfte werden mit dem Sprachmodell geprüft:{" "}
            {created.candidates} Kandidaten aus der Stichwortsuche und{" "}
            {created.sample} aus der Stichprobe. Die Treffer erscheinen nach und
            nach auf der Themenseite, solange als vorläufig. Ein Mensch schaltet
            das Thema danach frei.
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
            Verarbeitungsstand im Admin
          </Link>
        </p>
      </div>
    )
  }

  return (
    <div className="flex max-w-[68ch] flex-col gap-6">
      <div className="flex flex-col gap-2">
        <h1 className="font-heading text-2xl leading-tight font-semibold text-balance">
          Ad-hoc-Thema anlegen
        </h1>
        <p className="text-sm text-muted-foreground">
          Ein neues Thema ohne Neutraining: Du beschreibst es, das Sprachmodell
          schlägt Stichwörter vor, du prüfst sie. Danach sucht das System
          Kandidaten im ganzen Bestand und lässt sie vom Modell gegen deine
          Beschreibung prüfen.
        </p>
      </div>

      <section aria-labelledby="step1" className="flex flex-col gap-3">
        <h2 id="step1" className="font-heading text-lg font-medium">
          1 Thema beschreiben
        </h2>
        <label className="flex flex-col gap-1 text-xs text-muted-foreground">
          Name
          <Input
            value={title}
            maxLength={120}
            placeholder="z. B. Velowege"
            onChange={(event) => setTitle(event.target.value)}
          />
        </label>
        <label className="flex flex-col gap-1 text-xs text-muted-foreground">
          Beschreibung (was gehört dazu, was nicht?)
          <textarea
            className={TEXTAREA}
            value={description}
            maxLength={2000}
            onChange={(event) => setDescription(event.target.value)}
          />
        </label>
        <div>
          <Button
            variant="outline"
            size="sm"
            disabled={!nameOk || !descriptionOk || busy !== null}
            onClick={suggest}
          >
            {busy === "keywords"
              ? "Stichwörter werden vorgeschlagen …"
              : "Stichwörter vorschlagen"}
          </Button>
        </div>
      </section>

      <section aria-labelledby="step2" className="flex flex-col gap-3">
        <h2 id="step2" className="font-heading text-lg font-medium">
          2 Stichwörter prüfen
        </h2>
        <p className="text-xs text-muted-foreground">
          Ein Stichwort pro Zeile, Mehrwortbegriffe gelten als Phrase. Du kannst
          die Vorschläge ändern oder selbst eintragen.
        </p>
        <div className="grid gap-3 sm:grid-cols-3">
          {LANGUAGES.map((language) => (
            <label
              key={language.key}
              className="flex flex-col gap-1 text-xs text-muted-foreground"
            >
              {language.label}
              <textarea
                className={TEXTAREA}
                value={texts[language.key]}
                onChange={(event) => {
                  setTexts({ ...texts, [language.key]: event.target.value })
                  setPreview(undefined)
                }}
              />
            </label>
          ))}
        </div>
        <label className="flex max-w-xs flex-col gap-1 text-xs text-muted-foreground">
          Nur Geschäfte ab Datum (optional)
          <Input
            type="date"
            value={since}
            onChange={(event) => {
              setSince(event.target.value)
              setPreview(undefined)
            }}
          />
        </label>
        <div className="flex flex-wrap items-center gap-3">
          <Button
            variant="outline"
            size="sm"
            disabled={terms === 0 || busy !== null}
            onClick={estimate}
          >
            {busy === "preview" ? "Wird gezählt …" : "Treffer abschätzen"}
          </Button>
          <span className="text-xs text-muted-foreground">
            Zählt nur, legt nichts an.
          </span>
        </div>
        {preview && (
          <div role="status" className="flex flex-col gap-2 text-sm">
            <p>
              <span className="tabular font-semibold">
                {preview.candidates}
              </span>{" "}
              Geschäfte treffen die Stichwörter, dazu eine Stichprobe von{" "}
              <span className="tabular font-semibold">{preview.sample}</span>{" "}
              zur Kontrolle.
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
            {preview.candidates + preview.sample > LARGE_RUN && (
              <p className="text-xs text-level-medium">
                Das sind {preview.candidates + preview.sample} Prüfungen mit dem
                Sprachmodell und dauert entsprechend lange. Mit engeren
                Stichwörtern oder einem Datum wird der Lauf kleiner.
              </p>
            )}
            {preview.candidates === 0 && (
              <p className="text-xs text-muted-foreground">
                Keine Treffer: Die Stichwörter sind wohl zu eng oder zu selten.
              </p>
            )}
          </div>
        )}
      </section>

      <section aria-labelledby="step3" className="flex flex-col gap-3">
        <h2 id="step3" className="font-heading text-lg font-medium">
          3 Anlegen
        </h2>
        <label className="flex max-w-xs flex-col gap-1 text-xs text-muted-foreground">
          Verlinkt aus Kapitel (optional)
          <select
            value={broader}
            onChange={(event) => setBroader(event.target.value)}
            className="h-8 rounded-md border border-input bg-background px-2 text-sm text-foreground"
          >
            <option value="">Keinem Kapitel zugeordnet</option>
            {chapters.map((chapter) => (
              <option key={chapter.page_id} value={chapter.page_id}>
                {chapter.title}
              </option>
            ))}
          </select>
        </label>
        <p className="text-xs text-muted-foreground">
          Das Anlegen startet Läufe mit dem Sprachmodell. Das Thema bleibt
          «vorläufig», bis es jemand freischaltet. Gespeichert wird mit dem
          Namen «{name.trim() || "Admin"}».
        </p>
        <div>
          <Button
            disabled={!nameOk || !descriptionOk || terms === 0 || busy !== null}
            onClick={create}
          >
            {busy === "create"
              ? "Thema wird angelegt …"
              : "Thema anlegen und auswerten"}
          </Button>
        </div>
      </section>

      {error && (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      )}
    </div>
  )
}
