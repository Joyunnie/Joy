// --- Auth ---

export interface LoginRequest {
  pharmacy_id: number;
  username: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface AccessTokenResponse {
  access_token: string;
  token_type: string;
}

// --- Alerts ---

export interface AlertOut {
  id: number;
  alert_type: string;
  message: string;
  sent_at: string;
  read_at: string | null;
}

export interface AlertListResponse {
  alerts: AlertOut[];
  total: number;
}

// --- OTC Inventory ---

export interface OtcItemResponse {
  id: number;
  pharmacy_id: number;
  drug_id: number;
  drug_name: string | null;
  current_quantity: number;
  display_location: string | null;
  storage_location: string | null;
  last_counted_at: string | null;
  version: number;
  created_at: string;
  updated_at: string;
  is_low_stock: boolean;
  min_quantity: number | null;
}

export interface OtcListResponse {
  items: OtcItemResponse[];
  total: number;
}

// --- Narcotics Inventory ---

export interface NarcoticsItemResponse {
  id: number;
  pharmacy_id: number;
  drug_id: number;
  drug_name: string | null;
  lot_number: string;
  current_quantity: number;
  is_active: boolean;
  last_inspected_at: string | null;
  version: number;
  created_at: string;
  updated_at: string;
  is_low_stock: boolean;
  min_quantity: number | null;
}

export interface NarcoticsListResponse {
  items: NarcoticsItemResponse[];
  total: number;
}

// --- Prescription Inventory ---

export interface InventoryStatusItem {
  cassette_number: number;
  drug_name: string | null;
  current_quantity: number;
  min_quantity: number | null;
  is_low_stock: boolean;
  quantity_synced_at: string | null;
}

export interface InventoryStatusResponse {
  items: InventoryStatusItem[];
}

// --- Predictions ---

export interface NeededDrug {
  drug_name: string;
  quantity: number;
  in_stock: number | null;
}

export interface PredictionOut {
  id: number;
  patient_hash: string;
  predicted_visit_date: string;
  alert_date: string;
  alert_sent: boolean;
  prediction_method: string;
  based_on_visit_date: string | null;
  is_overdue: boolean;
  needed_drugs: NeededDrug[];
}

export interface PredictionListResponse {
  predictions: PredictionOut[];
}

// --- JWT payload ---

export interface JwtPayload {
  sub: string;
  pharmacy_id: number;
  role: string;
  type: string;
  iat: number;
  exp: number;
}
