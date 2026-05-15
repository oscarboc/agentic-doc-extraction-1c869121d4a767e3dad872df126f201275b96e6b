import os

import psycopg2

_conn = None

def get_connection():
    global _conn
    if _conn is None or getattr(_conn, 'closed', 1) != 0:
        db_url = os.getenv("DATABASE_URL")
        if not db_url:
            print("No se encontró la variable de entorno 'DATABASE_URL'. Configúrala primero.")
            return None
        try:
            _conn = psycopg2.connect(db_url)
        except Exception as e:
            print("Error al conectar a PostgreSQL:", e)
            return None
    return _conn


def verificar_conexion():
    conn = get_connection()
    if not conn:
        return

    try:
        cursor = conn.cursor()
        cursor.execute("SELECT 1;")
        resultado = cursor.fetchone()
        if resultado:
            print("La conexión con PostgreSQL funciona correctamente.")
        cursor.close()
    except Exception as e:
        print("Error al ejecutar query de verificación:", e)


def is_file_processed(filename: str) -> bool:
    conn = get_connection()
    if not conn:
        return False

    try:
        cursor = conn.cursor()

        cursor.execute(
            "SELECT 1 FROM billing_metadata WHERE filename = %s LIMIT 1;", (str(filename),)
        )
        result = cursor.fetchone()
        cursor.close()
        conn.commit() # Commit para finalizar cualquier transacción implícita
        return bool(result)
    except Exception as e:
        print("Error al verificar si el archivo fue procesado:", e)
        if conn:
            conn.rollback()
        return False


def save_billing_metadata(
    document_id: str,
    filename: str,
    extracted_pages: int,
    azure_model_id: str,
    tokens_input: int,
    tokens_output: int,
    processed_authorizations: int = 0,
):
    conn = get_connection()
    if not conn:
        print("No DATABASE_URL configured, skipping billing log.")
        return

    try:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS billing_metadata (
                id SERIAL PRIMARY KEY,
                document_id VARCHAR(255),
                filename VARCHAR(255),
                extracted_pages INT,
                azure_model_id VARCHAR(255),
                tokens_input INT,
                tokens_output INT,
                openai_tokens INT,
                processed_authorizations INT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        # Añadir las columnas si la tabla ya existía de antes
        cursor.execute("""
            ALTER TABLE billing_metadata 
            ADD COLUMN IF NOT EXISTS processed_authorizations INT DEFAULT 0;
        """)
        cursor.execute("""
            ALTER TABLE billing_metadata ADD COLUMN IF NOT EXISTS filename VARCHAR(255);
        """)
        cursor.execute("""
            ALTER TABLE billing_metadata ADD COLUMN IF NOT EXISTS tokens_input INT;
        """)
        cursor.execute("""
            ALTER TABLE billing_metadata ADD COLUMN IF NOT EXISTS tokens_output INT;
        """)
        cursor.execute("""
            ALTER TABLE billing_metadata DROP COLUMN IF EXISTS azure_credits_left;
        """)
        cursor.execute(
            """
            INSERT INTO billing_metadata 
            (document_id, filename, extracted_pages, azure_model_id, 
            tokens_input, tokens_output, processed_authorizations)
            VALUES (%s, %s, %s, %s, %s, %s, %s);
        """,
            (
                str(document_id),
                str(filename),
                extracted_pages,
                azure_model_id,
                tokens_input,
                tokens_output,
                processed_authorizations,
            ),
        )

        conn.commit()
        cursor.close()
        print(f"Facturación guardada para documento: {document_id}")
    except Exception as e:
        print("Error al guardar metadata de facturación:", e)
        if conn:
            conn.rollback()


if __name__ == "__main__":
    verificar_conexion()