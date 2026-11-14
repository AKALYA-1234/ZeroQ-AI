# ZeroQ AI - 19-Year Synthetic Manufacturing Quality Dataset

## Coverage
- Production batch timeline: 2008-01-01 through 2026-12-31 (19 calendar years).
- Complaint, investigation and action dates may extend into 2027 because reports and follow-up activities can occur after production.
- All records are synthetically generated for hackathon prototyping.
- This is NOT ABT-CPD's actual proprietary data and must not be represented as such.

## Files and record counts
- `products.csv`: 20 rows
- `customers.csv`: 500 rows
- `facilities.csv`: 5 rows
- `production_lines.csv`: 15 rows
- `materials.csv`: 40 rows
- `production_batches.csv`: 24,000 rows
- `complaints.csv`: 1,318 rows
- `quality_inspections.csv`: 37,245 rows
- `investigations.csv`: 1,029 rows
- `corrective_actions.csv`: 928 rows
- `data_dictionary.csv`: 12 rows

## Relational model
- products.product_id -> production_batches.product_id and complaints.product_id
- facilities.facility_id -> production_lines.facility_id and production_batches.facility_id
- production_lines.production_line_id -> production_batches.production_line_id
- materials.material_id -> production_batches.packaging_material_id and production_batches.raw_material_id
- customers.customer_id -> complaints.customer_id
- production_batches.batch_id -> complaints.batch_id and quality_inspections.batch_id
- complaints.complaint_id -> investigations.complaint_id
- investigations.investigation_id -> corrective_actions.investigation_id
- complaints.complaint_id -> corrective_actions.complaint_id

## Recommended usage
1. `products.csv`, `facilities.csv`, `production_lines.csv`, `materials.csv`, `customers.csv`: dimension/master tables.
2. `production_batches.csv`: central production fact table and source for batch-level pre-dispatch risk modelling.
3. `complaints.csv`: NLP classification, complaint trend analytics and complaint outcome labels.
4. `quality_inspections.csv`: inspection trend analysis and quality-feature engineering. Use only inspections completed before the prediction decision time.
5. `investigations.csv`: root-cause analysis, verified-cause evaluation and RAG source documents.
6. `corrective_actions.csv`: CAPA effectiveness and recurrence analysis.

## Important modelling cautions
- For pre-dispatch complaint prediction, do NOT use `complaint_count_linked`, `complaint_occurred`, complaint date, investigation data, or any information created after dispatch as input features.
- `complaint_occurred` is a synthetic outcome label derived from linked complaint records. It is suitable for a prototype baseline, but real deployment requires a clearly defined outcome window and production-volume-aware labels.
- Use a chronological split by production date (for example, train 2008-2021, validation 2022-2023, test 2024-2026), not a random row split.
- Complaint reports can be received days after production. Match complaints to batches using batch_id; do not use complaint receipt date as if it were the defect occurrence date.
- Root causes and corrective-action effectiveness are simulated labels. Validate all causal conclusions against actual investigation evidence in a real deployment.
- The data includes synthetic categorical and numeric patterns. Model performance on it does not demonstrate real-world predictive performance.

## Suggested first preprocessing steps
- Parse all date columns as dates.
- Check primary-key uniqueness and foreign-key integrity.
- Inspect missingness, category frequencies, outliers and year-wise volume.
- Build complaint rates using units produced as denominator where appropriate.
- Create time-aware historical features using only information available before each batch's prediction timestamp.
