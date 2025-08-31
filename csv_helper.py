import csv

def read_csv(file_path):
    """
    Reads a CSV file and returns its content as a list of dictionaries.
    
    :param file_path: Path to the CSV file.
    :return: List of dictionaries representing the CSV rows.
    """
    with open(file_path, mode='r', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        return [row for row in reader]
    
def write_csv(file_path, data, fieldnames):
    """
    Writes a list of dictionaries to a CSV file.
    
    :param file_path: Path to the CSV file.
    :param data: List of dictionaries to write to the CSV file.
    :param fieldnames: List of field names for the CSV file.
    """
    with open(file_path, mode='w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(data)

def append_csv(file_path, data, fieldnames):
    """
    Appends a list of dictionaries to a CSV file.
    
    :param file_path: Path to the CSV file.
    :param data: List of dictionaries to append to the CSV file.
    :param fieldnames: List of field names for the CSV file.
    """
    with open(file_path, mode='a', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writerows(data)

def csv_to_dict(file_path):
    """
    Converts a CSV file to a dictionary where the keys are the column headers.
    
    :param file_path: Path to the CSV file.
    :return: Dictionary with column headers as keys and lists of column values as values.
    """
    data = read_csv(file_path)
    if not data:
        return {}
    
    result = {key: [] for key in data[0].keys()}
    for row in data:
        for key, value in row.items():
            result[key].append(value)
    
    return result

