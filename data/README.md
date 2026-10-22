# Question Bank Dataset Documentation

This directory contains the question-answer dataset used by the **Adaptive Technical Viva & Oral Screener** backend.

---

## 📁 Dataset Schema

Questions can be imported from either **JSON** or **CSV** formats. Each normalized question record has the following fields:

| Field | Type | Required | Description | Example |
| :--- | :--- | :--- | :--- | :--- |
| `question_id` | String | Yes | Unique identifier for the question | `"OS001"` |
| `subject` | String | Yes | Core CS subject: `"OS"`, `"DBMS"`, or `"CN"` | `"OS"` |
| `topic` | String | Yes | Specific subject topic | `"Deadlocks"` |
| `difficulty` | String | Yes | Difficulty tier: `"easy"`, `"medium"`, or `"hard"` | `"medium"` |
| `question` | String | Yes | The oral viva question presented to the student | `"What is a deadlock?"` |
| `reference_answer` | String | Yes | Ground-truth reference answer for conceptual evaluation | `"A deadlock occurs when..."` |
| `key_concepts` | List[String] | Yes | Core technical concepts required for a complete answer | `["Mutual exclusion", "Hold and wait", ...]` |
| `tags` | List[String] | No | Optional classification tags | `["process_management", "concurrency"]` |

---

## 📥 Importing Datasets

Datasets can be imported using the standalone CLI script:

```bash
python scripts/import_dataset.py --file data/question_bank.json
```

Or for a CSV file:

```bash
python scripts/import_dataset.py --file data/custom_questions.csv --format csv
```

### Supported CSV Format
When using CSV, list fields like `key_concepts` and `tags` should be pipe-separated (`|`) or semicolon-separated (`;`):
```csv
question_id,subject,topic,difficulty,question,reference_answer,key_concepts,tags
OS001,OS,Deadlocks,easy,"What is a deadlock?","A deadlock occurs...","Mutual exclusion|Hold and wait|No preemption|Circular wait","concurrency|processes"
```

---

## 🔒 Security & Privacy

- **Never Expose Reference Answers:** The student-facing API endpoints strictly sanitize questions using `QuestionSafe` schema, omitting `reference_answer`, `key_concepts`, and internal difficulty ratings.
- **Ground Truth Integrity:** Inferred concepts or difficulty levels are explicitly marked, and synthetic questions are never invented or masqueraded as part of the verified dataset.
