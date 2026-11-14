# Data Directory

Place the synthetic dataset CSV files here for import.

## Expected Files

- `products.csv`
- `customers.csv`
- `facilities.csv`
- `production_lines.csv`
- `materials.csv`
- `production_batches.csv`
- `complaints.csv`
- `quality_inspections.csv`
- `investigations.csv`
- `corrective_actions.csv`
- `data_dictionary.csv`

## Import

```bash
python scripts/import_dataset.py
```

The import script will inspect column names, validate relationships, and import records.

