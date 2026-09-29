#incident log interface 
def get_menu_choice():
    print("\n=== Workplace Safety Incident Triage System ===")
    print("1. Log a new incident")
    print("2. View summary of all incidents")
    print("3. Query incidents by location")
    print("4. Exit")
    choice = input("Choose an option (1-4): ").strip()
    while choice not in ("1", "2", "3", "4"):
        choice = input("Invalid choice. Please enter 1, 2, 3 or 4: ").strip()
    return choice