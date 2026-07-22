import { FormEvent, useState } from "react";
import { api, type AddressResult } from "../api";

export function AddressSearch({
  onChoose,
}: {
  onChoose: (result: AddressResult) => void;
}) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<AddressResult[]>([]);
  const [message, setMessage] = useState("");
  const [searching, setSearching] = useState(false);

  async function search(event: FormEvent) {
    event.preventDefault();
    if (query.trim().length < 3) return;
    setSearching(true);
    setMessage("");
    try {
      const matches = await api.searchAddresses(query.trim());
      setResults(matches);
      if (!matches.length) setMessage("No matching places found. Try a broader search.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Address search failed.");
    } finally {
      setSearching(false);
    }
  }

  return (
    <div className="address-search">
      <form onSubmit={search}>
        <label>
          Search by address or place
          <input
            value={query}
            minLength={3}
            maxLength={200}
            placeholder="Street, city, or landmark"
            onChange={(event) => setQuery(event.target.value)}
          />
        </label>
        <button disabled={searching || query.trim().length < 3}>
          {searching ? "Searching…" : "Search"}
        </button>
      </form>
      {results.length > 0 && (
        <ul className="address-results">
          {results.map((result) => (
            <li key={`${result.latitude},${result.longitude}`}>
              <button type="button" onClick={() => onChoose(result)}>
                {result.label}
              </button>
            </li>
          ))}
        </ul>
      )}
      {message && <p role="status">{message}</p>}
      <p className="fine">Search text is sent to the configured geocoding service; saved coordinates stay in Airspace.</p>
    </div>
  );
}
