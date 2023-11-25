import json
import jsonschema

def load_schema_from_file(schema_file_path):
    with open(schema_file_path, "r") as schema_file:
        schema = json.load(schema_file)
    return schema

def validate_json(json_data, schema):
    try:
        jsonschema.validate(instance=json_data, schema=schema)
        print("Validation successful!")
    except jsonschema.exceptions.ValidationError as e:
        print(f"Validation failed: {e}")
    except json.decoder.JSONDecodeError as e:
        print(f"Error loading JSON data: {e}")

# Example usage
if __name__ == "__main__":
    # Load your JSON schema from a file
    schema_file_path = "settings_schema.json"  # Replace with the path to your schema file
    try:
        repo_settings_schema = load_schema_from_file(schema_file_path)
    except FileNotFoundError:
        print(f"Schema file not found at: {schema_file_path}")
        exit(1)

    # Load your JSON data from a file
    json_data_file_path = "settings_data.json"  # Replace with the path to your JSON data file
    try:
        with open(json_data_file_path, "r") as file:
            json_data = json.load(file)
    except FileNotFoundError:
        print(f"JSON data file not found at: {json_data_file_path}")
        exit(1)
    except json.decoder.JSONDecodeError as e:
        print(f"Error loading JSON data: {e}")
        exit(1)

    # Validate the JSON data against the schema
    validate_json(json_data, repo_settings_schema)
