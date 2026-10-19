import { useMemo } from "react"
import { useLocation, useNavigate } from "react-router"

/** Suchparameter der Adresse lesen und setzen. Statt useSearchParams, das einen Link zu
 * github.com ins Bundle bringt (scripts/check-web-dist.mjs). */
export function useQuery(): [URLSearchParams, (next: URLSearchParams) => void] {
  const { search } = useLocation()
  const navigate = useNavigate()
  const params = useMemo(() => new URLSearchParams(search), [search])
  return [params, (next) => navigate({ search: `?${next}` })]
}
