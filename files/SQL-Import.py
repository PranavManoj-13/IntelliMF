import pandas as pd
from sqlalchemy import create_engine

db_user = 'root'
db_password = '12345678'
db_host = 'localhost'
db_port = '3306'
db_name = 'MutualFundsData'

engine = create_engine(f'mysql+pymysql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}')

csv_file = '/Users/pranav/Pranav/acad./Vasanth26/DSC413/Del-1/data/processed/scheme_147622.csv'
df_nav = pd.read_csv(csv_file)

df_nav['date'] = pd.to_datetime(df_nav['date'], format='%d-%m-%Y')
df_nav['nav'] = df_nav['nav'].astype(float)
df_nav['scheme_code'] = df_nav['scheme_code'].astype(int)

df_nav.to_sql('Fact_NAV', con=engine, if_exists='append', index=False)

print("Data imported successfully into MySQL database.")