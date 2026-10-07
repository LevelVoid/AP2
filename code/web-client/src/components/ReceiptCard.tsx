import type { PurchaseComplete } from '../types';
import './ReceiptCard.scss';

function getAmountCharge(
  purchase: PurchaseComplete,
  closedMandateContent?: Record<string, unknown>,
): number {
  // Prefer price_cents from verify_checkout_receipt (the actually-charged amount).
  if (typeof purchase.price_cents === 'number' && purchase.price_cents > 0) {
    return purchase.price_cents / 100;
  }
  // Fall back to the closed payment mandate amount.
  const amountObj = closedMandateContent?.payment_amount as
    | { amount?: number }
    | undefined;
  const amountValue = amountObj?.amount;
  return typeof amountValue === 'number' ? amountValue / 100 : 0;
}

function getPaymentMethod(
  closedMandateContent?: Record<string, unknown>,
): string {
  const instrument = closedMandateContent?.payment_instrument as
    | Record<string, unknown>
    | undefined;
  if (instrument?.description && typeof instrument.description === 'string')
    return instrument.description;
  if (instrument?.type && typeof instrument.type === 'string')
    return instrument.type;
  return 'Card';
}

/** Resolve the best display name for the purchased item. */
function getItemDisplayName(
  purchase: PurchaseComplete,
  fallbackName?: string,
): string {
  return (
    purchase.item_name ||
    purchase.item_description ||
    fallbackName ||
    'Order'
  );
}

interface Props {
  purchase: PurchaseComplete;
  /** Fallback item name from chat context (lastSelectedItemName). */
  itemName?: string;
}

export function ReceiptCard({ purchase, itemName }: Props) {
  const closedMandateContent = purchase.closed_payment_mandate_content as
    | Record<string, unknown>
    | undefined;
  const amount = getAmountCharge(purchase, closedMandateContent);
  const paymentMethod = getPaymentMethod(closedMandateContent);
  const displayName = getItemDisplayName(purchase, itemName);
  const imageUrl = purchase.image_url || '';

  return (
    <div className="msg-agent receipt-card-container">
      <div className="receipt-card">
        <div className="success-header">
          <div className="success-badge">
            <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
              <path
                d="M4 9l3.5 3.5 6.5-7"
                stroke="white"
                strokeWidth="2"
                strokeLinecap="round"
                strokeDasharray="24"
                strokeDashoffset="0"
              />
            </svg>
          </div>
          <div className="title-container">
            <div className="title">Purchase Complete</div>
            <div className="subtitle">Autonomous · mandate-authorized</div>
          </div>
        </div>

        <div className="receipt-body">
          {/* ── Item image (Task 3) ─────────────────────────────── */}
          {imageUrl && (
            <div className="item-image-wrapper">
              <img
                className="item-image"
                src={imageUrl}
                alt={displayName}
                onError={(e) => {
                  (e.target as HTMLImageElement).style.display = 'none';
                }}
              />
            </div>
          )}

          {/* ── Item name (Task 3) ──────────────────────────────── */}
          <div className="display-name">{displayName}</div>
          <div className="order-id">{purchase.order_id}</div>

          <div className="info-grid">
            <div className="grid-item">
              <div className="item-label">Charged</div>
              {/* ── Price from receipt (Task 3) ────────────────── */}
              <div className="item-value">${amount.toFixed(2)}</div>
            </div>
            <div className="grid-item">
              <div className="item-label">Payment</div>
              <div className="item-value payment-method">{paymentMethod}</div>
            </div>
          </div>

          <div className="chain-box">
            <div className="chain-label">Transaction chain</div>
            {[
              {
                label: 'Merchant MCP',
                steps: 'check_product → cart → checkout → complete',
              },
              {
                label: 'Credential Provider MCP',
                steps: 'issue_payment_credential (verify + issue)',
              },
            ].map((s) => (
              <div key={s.label} className="chain-row">
                <span className="row-label">{s.label}</span>
                <span className="row-value">{s.steps}</span>
              </div>
            ))}
          </div>

          <div className="timestamp">
            {new Date().toLocaleString('en-US', {
              month: 'short',
              day: 'numeric',
              year: 'numeric',
              hour: '2-digit',
              minute: '2-digit',
              timeZoneName: 'short',
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
