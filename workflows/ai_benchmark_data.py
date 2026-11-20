
# Controlled benchmark inventory.
# Synthetic evaluation data only.
# These are not real university inventory records.

BENCHMARK_ASSETS = [
    {
        "id": "MON-001",
        "name": "Dell Monitor",
        "description": "24-inch monitor for programming",
        "category": "IT Equipment",
        "department": "Computer Science",
        "location": "CS Lab",
        "available_quantity": 3,
    },
    {
        "id": "MON-002",
        "name": "Samsung Monitor",
        "description": "27-inch display for computer work",
        "category": "IT Equipment",
        "department": "Computer Science",
        "location": "CS Lab",
        "available_quantity": 2,
    },
    {
        "id": "LAP-001",
        "name": "Dell Laptop",
        "description": "Portable laptop for coding and software development",
        "category": "Computers",
        "department": "Engineering",
        "location": "Engineering Lab",
        "available_quantity": 4,
    },
    {
        "id": "LAP-002",
        "name": "HP Laptop",
        "description": "Laptop suitable for student programming projects",
        "category": "Computers",
        "department": "Computer Science",
        "location": "CS Lab",
        "available_quantity": 2,
    },
    {
        "id": "PRO-001",
        "name": "Epson Projector",
        "description": "Projector for classroom presentations",
        "category": "Presentation Equipment",
        "department": "Engineering",
        "location": "Lecture Hall",
        "available_quantity": 2,
    },
    {
        "id": "PRO-002",
        "name": "BenQ Projector",
        "description": "Projector for displaying lecture slides",
        "category": "Presentation Equipment",
        "department": "Computer Science",
        "location": "Lecture Room",
        "available_quantity": 1,
    },
    {
        "id": "CHR-001",
        "name": "Office Chair",
        "description": "Ergonomic chair for desk seating",
        "category": "Furniture",
        "department": "Administration",
        "location": "Office",
        "available_quantity": 5,
    },
    {
        "id": "CHR-002",
        "name": "Study Chair",
        "description": "Chair for student study spaces",
        "category": "Furniture",
        "department": "Computer Science",
        "location": "Study Area",
        "available_quantity": 6,
    },
]

BENCHMARK_CASES = [
    {
        "need": "I need a laptop for programming",
        "relevant_ids": ["LAP-001", "LAP-002"],
    },
    {
        "need": "I need a projector for classroom presentations",
        "relevant_ids": ["PRO-001", "PRO-002"],
    },
    {
        "need": "I need a chair for studying",
        "relevant_ids": ["CHR-001", "CHR-002"],
    },
    {
        "need": "I need an external monitor for computer work",
        "relevant_ids": ["MON-001", "MON-002"],
    },
]
