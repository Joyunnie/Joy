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

// --- Drug Search ---

export interface DrugOut {
  id: number;
  standard_code: string;
  name: string;
  category: string;
}

export interface DrugListResponse {
  items: DrugOut[];
  total: number;
}

// --- OTC Request Types ---

export interface OtcCreateRequest {
  drug_id: number;
  current_quantity: number;
  display_location?: string | null;
  storage_location?: string | null;
}

export interface OtcUpdateRequest {
  current_quantity: number;
  display_location?: string | null;
  storage_location?: string | null;
  version: number;
}

// --- Alert Read ---

export interface AlertReadResponse {
  id: number;
  read_at: string;
}

// --- Thresholds ---

export interface ThresholdItemResponse {
  id: number;
  pharmacy_id: number;
  drug_id: number;
  drug_name: string | null;
  drug_category: string | null;
  min_quantity: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface ThresholdListResponse {
  items: ThresholdItemResponse[];
  total: number;
}

export interface ThresholdCreateRequest {
  drug_id: number;
  min_quantity: number;
}

export interface ThresholdUpdateRequest {
  min_quantity: number;
  is_active: boolean;
}

// --- Shelf Layouts ---

export interface ShelfLayoutResponse {
  id: number;
  pharmacy_id: number;
  name: string;
  location_type: 'DISPLAY' | 'STORAGE';
  rows: number;
  cols: number;
  created_at: string;
  updated_at: string;
}

export interface ShelfLayoutListResponse {
  items: ShelfLayoutResponse[];
}

export interface ShelfLayoutCreateRequest {
  name: string;
  location_type: 'DISPLAY' | 'STORAGE';
  rows: number;
  cols: number;
}

export interface ShelfLayoutUpdateRequest {
  name: string;
  rows: number;
  cols: number;
}

export interface LocationAssignment {
  item_id: number;
  row: number;
  col: number;
}

export interface BatchLocationRequest {
  layout_id: number;
  assignments: LocationAssignment[];
}

export interface BatchLocationRemoveRequest {
  layout_id: number;
  item_ids: number[];
}

// --- Receipt OCR ---

export interface ReceiptOcrItemOut {
  id: number;
  record_id: number;
  drug_id: number | null;
  item_name: string | null;
  quantity: number | null;
  unit_price: number | null;
  confidence: number | null;
  match_score: number | null;
  matched_drug_name: string | null;
  is_confirmed: boolean;
  confirmed_drug_id: number | null;
  confirmed_quantity: number | null;
}

export interface ReceiptOcrRecordOut {
  id: number;
  pharmacy_id: number;
  image_path: string | null;
  ocr_status: string;
  supplier_name: string | null;
  receipt_date: string | null;
  receipt_number: string | null;
  total_amount: number | null;
  intake_status: string;
  confirmed_at: string | null;
  duplicate_of: number | null;
  ocr_engine: string | null;
  processed_at: string | null;
  created_at: string;
  item_count: number;
}

export interface ReceiptOcrResponse {
  record: ReceiptOcrRecordOut;
  items: ReceiptOcrItemOut[];
  duplicate_warning: string | null;
}

export interface ReceiptOcrDetailResponse {
  record: ReceiptOcrRecordOut;
  items: ReceiptOcrItemOut[];
  raw_text: string | null;
}

export interface ReceiptListResponse {
  items: ReceiptOcrRecordOut[];
  total: number;
}

export interface ConfirmResponse {
  confirmed_count: number;
  updated_stocks: Array<{
    drug_id: number;
    drug_name: string;
    table: string;
    added_quantity: number;
    new_quantity: number;
  }>;
}

export interface ReceiptItemUpdateRequest {
  drug_id?: number | null;
  quantity?: number | null;
}

// --- Prescription OCR ---

export interface PrescriptionOcrDrugOut {
  id: number;
  record_id: number;
  drug_id: number | null;
  drug_name_raw: string | null;
  dosage: string | null;
  frequency: string | null;
  days: number | null;
  total_quantity: number | null;
  confidence: number | null;
  match_score: number | null;
  matched_drug_name: string | null;
  is_narcotic: boolean;
  is_confirmed: boolean;
  confirmed_drug_id: number | null;
  confirmed_dosage: string | null;
  confirmed_frequency: string | null;
  confirmed_days: number | null;
}

export interface PrescriptionOcrRecordOut {
  id: number;
  pharmacy_id: number;
  image_path: string | null;
  ocr_status: string;
  patient_name: string | null;
  patient_dob: string | null;
  insurance_type: string | null;
  prescriber_name: string | null;
  prescriber_clinic: string | null;
  prescription_date: string | null;
  prescription_number: string | null;
  ocr_engine: string | null;
  confirmed_at: string | null;
  duplicate_of: number | null;
  processed_at: string | null;
  created_at: string;
  drug_count: number;
}

export interface PrescriptionOcrResponse {
  record: PrescriptionOcrRecordOut;
  drugs: PrescriptionOcrDrugOut[];
  duplicate_warning: string | null;
}

export interface PrescriptionOcrDetailResponse {
  record: PrescriptionOcrRecordOut;
  drugs: PrescriptionOcrDrugOut[];
  raw_text: string | null;
}

export interface PrescriptionListResponse {
  items: PrescriptionOcrRecordOut[];
  total: number;
}

export interface PrescriptionConfirmResponse {
  confirmed_count: number;
}

export interface PrescriptionDrugUpdateRequest {
  drug_id?: number | null;
  dosage?: string | null;
  frequency?: string | null;
  days?: number | null;
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
