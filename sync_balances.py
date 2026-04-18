import pandas as pd
import snowflake.connector
from database_snowflake import SNOW_ACCOUNT, SNOW_USER, SNOW_PASSWORD, SNOW_DATABASE, SNOW_SCHEMA, SNOW_WH, SNOW_ROLE

def sync_data():
    # 1. Read Excel
    print("Reading Excel data...")
    df = pd.read_excel('Emp_data.xlsx')
    
    # 2. Connect to Snowflake
    print("Connecting to Snowflake...")
    conn = snowflake.connector.connect(
        user=SNOW_USER,
        password=SNOW_PASSWORD,
        account=SNOW_ACCOUNT,
        warehouse=SNOW_WH,
        database=SNOW_DATABASE,
        schema=SNOW_SCHEMA,
        role=SNOW_ROLE
    )
    cur = conn.cursor()
    
    try:
        # 3. Update each employee
        for index, row in df.iterrows():
            emp_name = row['emp_name']
            total = float(row.get('Total_leaves', 14))
            rem = float(row.get('Remaining_Leaves', 14))
            taken = float(row.get('Leaves_This_Year', 0))
            carried = float(row.get('Leaves_Carried_Forward', 0))
            wfh = float(row.get('WFH_count', 0))
            phone = str(row.get('phone', ''))
            
            sql = """
            UPDATE ADLABS.AHSAN.EMPLOYEES 
            SET TOTAL_LEAVES = %s, 
                REMAINING_LEAVES = %s, 
                LEAVES_THIS_YEAR = %s, 
                LEAVES_CARRIED_FORWARD = %s,
                WFH_COUNT = %s,
                PHONE = %s
            WHERE LOWER(EMP_NAME) = LOWER(%s)
            """
            cur.execute(sql, (total, rem, taken, carried, wfh, phone, emp_name))
        
        conn.commit()
        print(f"Successfully synced {len(df)} employees to Snowflake!")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    sync_data()
