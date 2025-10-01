import os
import logging
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from urllib.parse import quote_plus
import pandas as pd
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Timestamp for filenames
timestamp = datetime.now().strftime('%Y%m%d')

# Email utility
def send_email(subject, msg_body):
    try:
        sender_email = os.getenv("SMTP_USER")
        receiver_email = os.getenv("SMTP_RECEIVER")
        email_password = os.getenv("SMTP_PASSWORD")
        smtp_server = os.getenv("SMTP_SERVER")

        msg = MIMEMultipart()
        msg["From"] = sender_email
        msg["To"] = receiver_email
        msg["Subject"] = subject
        msg.attach(MIMEText(msg_body, "plain"))

        recipients = receiver_email
        with smtplib.SMTP(smtp_server, 587) as server:
            server.starttls()
            server.login(sender_email, email_password)
            server.sendmail(sender_email, recipients, msg.as_string())

        logging.info("Email sent successfully.")
    except Exception as e:
        logging.error(f"Failed to send email: {e}")

# Base class for bag extraction
class BagExtractor:
    def __init__(self, organization, output_dir, output_filename, query):
        self.host = os.getenv("DB_HOST")
        self.user = os.getenv("DB_USER")
        raw_password = os.getenv("DB_PASSWORD")
        self.password = quote_plus(raw_password) if raw_password else ""
        self.database = os.getenv("DB_NAME2")
        self.output_dir = output_dir
        self.output_filename = output_filename
        self.output_path = os.path.join(self.output_dir, self.output_filename)
        self.organization = organization
        self.query = query

    def extract(self):
        try:
            engine = create_engine(f"mysql+mysqlconnector://{self.user}:{self.password}@{self.host}/{self.database}")
            df = pd.read_sql(self.query, engine)
            os.makedirs(self.output_dir, exist_ok=True)
            df.to_excel(self.output_path, index=False)
            logging.info(f"{self.organization}: Successfully saved query results to {self.output_path}")
            return df
        except Exception as e:
            logging.error(f"{self.organization}: Error during extraction - {e}")
            return None

# Class to get the latest order date
class OrderDateChecker:
    def __init__(self):
        self.host = os.getenv("DB_HOST")
        self.user = os.getenv("DB_USER")
        raw_password = os.getenv("DB_PASSWORD")
        self.password = quote_plus(raw_password) if raw_password else ""
        self.database = os.getenv("DB_NAME1")

    def get_latest_order_date(self):
        try:
            engine = create_engine(f"mysql+mysqlconnector://{self.user}:{self.password}@{self.host}/{self.database}")
            query = "SELECT DATE(`OrderDate`) AS `Order Date` FROM th_dw.matbag_neworders ORDER BY `OrderDate` DESC LIMIT 1;"
            df = pd.read_sql(query, engine)
            return pd.to_datetime(df['Order Date']).dt.date[0]
        except Exception as e:
            logging.error(f"Error fetching latest order date: {e}")
            return None

# SQL queries (replace with actual SQL from your original script)
GEMS_QUERY = """WITH MultipleBirth AS 
(SELECT FileNumber
       ,IdNumber
       ,MemberNumber
       ,DependentCode
       ,MultipleBirth
 FROM `th_dw`.member_multiplebirth
WHERE DeletedFile = 'No'
  AND FileRank = '1')


,NewOrders AS
(SELECT CAST(`tmc-live`.files.FileOpenDate AS DATE) AS 'RegistrationDate'
      ,CAST(`tmc-live`.files.Created AS DATE) AS 'CreatedDate'
      ,CAST(CURDATE() AS DATE) AS 'TodaysDate'
	  ,LTRIM(RTRIM(`tmc-live`.files.ReferenceNumber)) AS 'FileNumber'
      ,LTRIM(RTRIM(`tmc-live`.membermedicalaids.SchemeNumber)) AS 'MembershipNumber'
      ,LTRIM(RTRIM(`tmc-live`.members.DependentCode)) AS 'DependantCode'
      ,LTRIM(RTRIM(`tmc-live`.members.FirstName)) AS 'Name'
	  ,LTRIM(RTRIM(`tmc-live`.memberdetails.Surname)) AS 'Surname'
      ,CASE WHEN `tmc-live`.members.IdNumber IS NOT NULL THEN `tmc-live`.members.IdNumber
            ELSE `tmc-live`.members.Passport
            END AS 'IDNumber'
      ,CAST(`tmc-live`.members.DateOfBirth AS DATE) AS 'DateofBirth'
      ,'Gems' AS 'Organization'
      ,CASE `tmc-live`.tenantschemeoptionsconfigs.name
				       WHEN 'Sapphire' THEN 'Sapphire'
					   WHEN 'Beryl' THEN 'Beryl'
					   WHEN 'Ruby' THEN 'Ruby'
					   WHEN 'Emerald' THEN 'Emerald'
                       WHEN 'Emerald ' THEN 'Emerald'
					   WHEN 'Onyx' THEN 'Onyx'
					   WHEN 'Emerald Value Option ' THEN 'Emerald Value Option'
                       WHEN 'Emerald Value Option' THEN 'Emerald Value Option'
                       WHEN 'Emerald Value' THEN 'Emerald Value'
					   WHEN 'Tanzanite One' THEN 'Tanzanite One' 
                       WHEN 'Tanzanite 1' THEN 'Tanzanite One' 
                       END AS 'Option'
      ,CAST(`tmc-live`.files.EDD AS DATE) AS 'EDD'
      ,ROUND(40-(DATEDIFF(`tmc-live`.files.EDD, CURDATE())/7)) AS 'Week'
      ,LTRIM(RTRIM(`tmc-live`.memberdetails.ContactNumber)) AS 'CellNo'
      ,LTRIM(RTRIM(`tmc-live`.addresses.Physical)) AS 'Address1'
      ,LTRIM(RTRIM(`tmc-live`.addresses.Postal)) AS 'Address2'
      ,LTRIM(RTRIM(`tmc-live`.addresses.PhysicalCode)) AS 'PostalCode'
      ,`tmc-live`.files.FileStatus AS 'FileStatus'
      ,ROW_NUMBER()OVER(PARTITION BY `tmc-live`.membermedicalaids.SchemeNumber, `tmc-live`.members.DependentCode ORDER BY `tmc-live`.files.Created DESC) AS 'Rank'
    
FROM `tmc-live`.members
JOIN `tmc-live`.membermedicalaids
  ON `tmc-live`.members.membermedicalaidId = `tmc-live`.membermedicalaids.Id
JOIN `tmc-live`.files
  ON `tmc-live`.members.Id = `tmc-live`.files.MemberId
JOIN `tmc-live`.memberdetails
  ON `tmc-live`.files.MemberDetailId = `tmc-live`.memberdetails.Id
JOIN `tmc-live`.tenantschemeoptionsconfigs
  ON `tmc-live`.membermedicalaids.SchemeOption = `tmc-live`.tenantschemeoptionsconfigs.Id
JOIN `tmc-live`.tenants
 ON `tmc-live`.files.TenantId = `tmc-live`.tenants.Id
JOIN `tmc-live`.addresses
  ON `tmc-live`.memberdetails.AddressId = `tmc-live`.addresses.id
  

WHERE `tmc-live`.files.ReferenceNumber NOT IN (SELECT DISTINCT FileNumber FROM `th_dw`.matbag_neworders)
  AND `tmc-live`.files.Deleted = 0 
  AND `tmc-live`.members.MemberStatus = 'Active'
  AND `tmc-live`.files.FileStatus = 'Approved'
  AND `tmc-live`.tenants.name = 'Tshela'
  AND ROUND(40-(DATEDIFF(`tmc-live`.files.EDD, CURDATE())/7)) BETWEEN '26' AND '52'
  AND `tmc-live`.membermedicalaids.SchemeNumber NOT IN ('001206857','321654','001660649','001791026') -- "Member Request to not receive bag", "test file", "Member Request to not receive bag"
  AND `tmc-live`.files.ReferenceNumber NOT IN ('00154564','00152448','00154555','00154564','00153366','00149421','00149261','00131603','00138904','00137460','00135895','00133859','00133127','00131789','00124027','00115373','00122997','00122696','00122251','00120735','00119031','00117012','00118508','00111701','00117921','00117099','00116514','00115691','00114396','00104745','00113924','00111243','00109060','00106306','00106081','00103713','00103761','00093910','00101050','00100405','00098169','00096667','00093843','00094563','00061374','00073128','00073299','00075462','00078626','00089085','00089991','00092644') ) -- 1 Duplicate file. 2&3 "Member Request to not receive bag" 4.Member received previous bag order(miscarrige) 5&6. Member number and file number changed.
  
 SELECT  NewOrders.RegistrationDate AS 'Registration Date'
        ,NewOrders.CreatedDate AS 'CreatedDate'
        ,NewOrders.TodaysDate AS 'Todays Date'
        ,NewOrders.FileNumber AS 'File Number'
        ,NewOrders.MembershipNumber AS 'Membership Number'
        ,NewOrders.DependantCode AS 'Dependant Code'
        ,CASE WHEN MultipleBirth.MultipleBirth IS NULL THEN '1'
              ELSE MultipleBirth.MultipleBirth 
              END AS 'Multiple Birth'
        ,NewOrders.Name AS 'Name'
        ,NewOrders.Surname AS 'Surname'
        ,NewOrders.IDNumber AS 'IDNumber'
        ,NewOrders.DateofBirth AS 'Date of Birth'
        ,NewOrders.Organization AS 'Organization'
        ,NewOrders.Option AS 'Option'
        ,NewOrders.EDD AS 'EDD'
        ,NewOrders.Week AS 'Week'
        ,NewOrders.CellNo AS 'Cell No'
        ,NewOrders.Address1 AS 'Address 1'
        ,NewOrders.Address2 AS 'Address 2'
        ,NewOrders.PostalCode AS 'Postal Code'
        ,NewOrders.FileStatus AS 'File Status'
        
  
     FROM NewOrders
LEFT JOIN MultipleBirth
	   ON NewOrders.FileNumber = MultipleBirth.FileNumber;"""
SAM_QUERY = """WITH MultipleBirth AS 
(SELECT FileNumber
       ,IdNumber
       ,MemberNumber
       ,DependentCode
       ,MultipleBirth
 FROM `th_dw`.member_multiplebirth
WHERE DeletedFile = 'No'
  AND FileRank = '1')


,NewOrders AS
(SELECT CAST(`tmc-live`.files.FileOpenDate AS DATE) AS 'RegistrationDate'
      ,CAST(`tmc-live`.files.Created AS DATE) AS 'CreatedDate'
      ,CAST(CURDATE() AS DATE) AS 'TodaysDate'
	  ,LTRIM(RTRIM(`tmc-live`.files.ReferenceNumber)) AS 'FileNumber'
      ,LTRIM(RTRIM(`tmc-live`.membermedicalaids.SchemeNumber)) AS 'MembershipNumber'
      ,LTRIM(RTRIM(`tmc-live`.members.DependentCode)) AS 'DependantCode'
      ,LTRIM(RTRIM(`tmc-live`.members.FirstName)) AS 'Name'
	  ,LTRIM(RTRIM(`tmc-live`.memberdetails.Surname)) AS 'Surname'
      ,CASE WHEN `tmc-live`.members.IdNumber IS NOT NULL THEN `tmc-live`.members.IdNumber
            ELSE `tmc-live`.members.Passport
            END AS 'IDNumber'
      ,CAST(`tmc-live`.members.DateOfBirth AS DATE) AS 'DateofBirth'
      ,`tmc-live`.tenants.name AS 'Organization'
      ,`tmc-live`.tenantschemeoptionsconfigs.name AS 'Option'
      ,CAST(`tmc-live`.files.EDD AS DATE) AS 'EDD'
      ,ROUND(40-(DATEDIFF(`tmc-live`.files.EDD, CURDATE())/7)) AS 'Week'
      ,LTRIM(RTRIM(`tmc-live`.memberdetails.ContactNumber)) AS 'CellNo'
      ,LTRIM(RTRIM(`tmc-live`.addresses.Physical)) AS 'Address1'
      ,LTRIM(RTRIM(`tmc-live`.addresses.Postal)) AS 'Address2'
      ,LTRIM(RTRIM(`tmc-live`.addresses.PhysicalCode)) AS 'PostalCode'
      ,`tmc-live`.files.FileStatus AS 'FileStatus'
      ,ROW_NUMBER()OVER(PARTITION BY `tmc-live`.membermedicalaids.SchemeNumber, `tmc-live`.members.DependentCode ORDER BY `tmc-live`.files.Created DESC) AS 'Rank'
    
FROM `tmc-live`.members
JOIN `tmc-live`.membermedicalaids
  ON `tmc-live`.members.membermedicalaidId = `tmc-live`.membermedicalaids.Id
JOIN `tmc-live`.files
  ON `tmc-live`.members.Id = `tmc-live`.files.MemberId
JOIN `tmc-live`.memberdetails
  ON `tmc-live`.files.MemberDetailId = `tmc-live`.memberdetails.Id
JOIN `tmc-live`.tenantschemeoptionsconfigs
  ON `tmc-live`.membermedicalaids.SchemeOption = `tmc-live`.tenantschemeoptionsconfigs.Id
JOIN `tmc-live`.tenants
 ON `tmc-live`.files.TenantId = `tmc-live`.tenants.Id
JOIN `tmc-live`.addresses
  ON `tmc-live`.memberdetails.AddressId = `tmc-live`.addresses.id
  

WHERE `tmc-live`.files.ReferenceNumber NOT IN (SELECT DISTINCT FileNumber FROM `th_dw`.matbag_neworders)
  AND `tmc-live`.files.Deleted = 0 
  AND `tmc-live`.members.MemberStatus = 'Active'
  AND `tmc-live`.files.FileStatus = 'Approved'
  AND `tmc-live`.tenants.name = 'Samwumed'
  AND ROUND(40-(DATEDIFF(`tmc-live`.files.EDD, CURDATE())/7)) BETWEEN '26' AND '52' )
  
 SELECT  NewOrders.RegistrationDate AS 'Registration Date'
        ,NewOrders.CreatedDate AS 'CreatedDate'
        ,NewOrders.TodaysDate AS 'Todays Date'
        ,NewOrders.FileNumber AS 'File Number'
        ,NewOrders.MembershipNumber AS 'Membership Number'
        ,NewOrders.DependantCode AS 'Dependant Code'
        ,CASE WHEN MultipleBirth.MultipleBirth IS NULL THEN '1'
              ELSE MultipleBirth.MultipleBirth 
              END AS 'Multiple Birth'
        ,NewOrders.Name AS 'Name'
        ,NewOrders.Surname AS 'Surname'
        ,NewOrders.IDNumber AS 'IDNumber'
        ,NewOrders.DateofBirth AS 'Date of Birth'
        ,NewOrders.Organization AS 'Organization'
        ,NewOrders.Option AS 'Option'
        ,NewOrders.EDD AS 'EDD'
        ,NewOrders.Week AS 'Week'
        ,NewOrders.CellNo AS 'Cell No'
        ,NewOrders.Address1 AS 'Address 1'
        ,NewOrders.Address2 AS 'Address 2'
        ,NewOrders.PostalCode AS 'Postal Code'
        ,NewOrders.FileStatus AS 'File Status'
        
  
     FROM NewOrders
LEFT JOIN MultipleBirth
	   ON NewOrders.FileNumber = MultipleBirth.FileNumber"""

# Instantiate objects
gems_extractor = BagExtractor("GEMS", "Gems Bags", f"Logistic Service Management Report {timestamp}.xlsx", GEMS_QUERY)
sam_extractor = BagExtractor("SAMWUMED", "Samwumed Bags", f"Logistic Service Management Report SAM {timestamp}.xlsx", SAM_QUERY)
date_checker = OrderDateChecker()

# Determine day of week
day_of_week = datetime.now().weekday()
latest_order_date = date_checker.get_latest_order_date()

# Determine expected date based on day
expected_date = datetime.now().date() - timedelta(days=1)
if day_of_week == 0:  # Monday
    expected_date = datetime.now().date() - timedelta(days=3)

# Execute based on day
if latest_order_date == expected_date:
    if day_of_week == 3:  # Thursday
        send_email("Maternity Bags", "Data Loaded yesterday! Continue with GEMS and SAMWUMED Bags")
        gems_extractor.extract()
        sam_extractor.extract()
    else:
        send_email("Maternity Bags", "Data Loaded yesterday! Continue with GEMS Bags")
        gems_extractor.extract()
else:
    send_email("Maternity Bags", "Data not loaded yesterday! Please check the database")