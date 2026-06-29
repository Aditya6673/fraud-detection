import { useMemo, useState } from 'react';

type TransactionForm = {
  customerId: string;
  cardId: string;
  amount: string;
  currency: string;
  merchant: string;
  merchantCategory: string;
  location: string;
  latitude: string;
  longitude: string;
  timestamp: string;
};

type ScoreResponse = {
  transactionId?: string;
  riskScore: number;
  status: string;
  reasons: string[];
  modelVersion: string;
  mlAvailable: boolean;
  timestamp?: string;
};

const initialForm: TransactionForm = {
  customerId: 'cust-001',
  cardId: 'card-001',
  amount: '250.00',
  currency: 'USD',
  merchant: 'Northwind Market',
  merchantCategory: 'retail',
  location: 'Seattle',
  latitude: '47.6062',
  longitude: '-122.3321',
  timestamp: new Date().toISOString(),
};

const API_BASE = 'http://localhost:8080';
const FRAUD_API_BASE = 'http://localhost:8000';

async function createTransaction(form: TransactionForm) {
  const payload = {
    customerId: form.customerId,
    cardId: form.cardId,
    amount: Number(form.amount),
    currency: form.currency,
    merchant: form.merchant,
    merchantCategory: form.merchantCategory,
    location: form.location,
    latitude: Number(form.latitude),
    longitude: Number(form.longitude),
    timestamp: form.timestamp,
  };

  const response = await fetch(`${API_BASE}/api/v1/transactions`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Idempotency-Key': crypto.randomUUID(),
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error('Transaction submission failed');
  }

  return response.json();
}

async function scoreTransaction(payload: Record<string, unknown>) {
  const response = await fetch(`${FRAUD_API_BASE}/api/v1/score/`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error('Fraud scoring failed');
  }

  return response.json() as Promise<ScoreResponse>;
}

export default function App() {
  const [form, setForm] = useState(initialForm);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState<ScoreResponse | null>(null);

  const statusTone = useMemo(() => {
    if (!result) return '';
    if (result.status === 'BLOCKED') return 'status blocked';
    if (result.status === 'REVIEW') return 'status review';
    return 'status approved';
  }, [result]);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError('');
    setResult(null);

    try {
      const transactionResult = await createTransaction(form);
      const score = await scoreTransaction({
        transactionId: transactionResult.transactionId,
        customerId: form.customerId,
        cardId: form.cardId,
        amount: Number(form.amount),
        currency: form.currency,
        merchant: form.merchant,
        merchantCategory: form.merchantCategory,
        location: form.location,
        latitude: Number(form.latitude),
        longitude: Number(form.longitude),
        timestamp: form.timestamp,
      });

      setResult(score);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unexpected error');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="app-shell">
      <header>
        <h1>Fraud Detection Console</h1>
        <p>Submit a transaction and review the fraud score from the backend services.</p>
      </header>

      <form onSubmit={handleSubmit} className="card">
        <h2>New transaction</h2>
        {Object.entries(form).map(([key, value]) => (
          <label key={key} className="field">
            <span>{key}</span>
            <input
              value={value}
              onChange={(event) => setForm((current) => ({ ...current, [key]: event.target.value }))}
              required={key !== 'merchantCategory'}
            />
          </label>
        ))}
        <button type="submit" disabled={loading}>
          {loading ? 'Submitting...' : 'Submit transaction'}
        </button>
      </form>

      {error ? <div className="card error">{error}</div> : null}

      {result ? (
        <div className="card result">
          <h2>Fraud assessment</h2>
          <div className={statusTone}>
            <strong>Status:</strong> {result.status}
          </div>
          <p>
            <strong>Risk score:</strong> {result.riskScore}
          </p>
          <p>
            <strong>Model version:</strong> {result.modelVersion}
          </p>
          <p>
            <strong>ML available:</strong> {result.mlAvailable ? 'Yes' : 'No'}
          </p>
          <ul>
            {result.reasons.map((reason) => (
              <li key={reason}>{reason}</li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}
