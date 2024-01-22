import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO
import regex as re
import requests
import urllib3
urllib3.disable_warnings()

APIKEY = '5ab4064c-e88a-40c0-9358-290709f22db0'


#%% Functions
def clean_phone_number(phone):
    # Remove phone extension and non-numeric characters
    clean_phone = re.sub('^\+','',re.sub('[^0-9]','',re.split(' [a-z]+.+',phone)[0]))
    if pd.isna(clean_phone) or clean_phone.startswith(('800', '844', '888')) or len(clean_phone)>11 or (clean_phone==''):
        return None
    
    # If # has an extension, re include it
    if 'ext' in phone or bool(re.search('x\s?\d+',phone,flags=re.I)):
        # clean_phone = clean_phone + ' ext. ' + re.sub('[^\d+$]','',re.search('(ext\.?|x?)\s?\d+$',phone,flags=re.I)[0])
        clean_phone = None

    elif len(clean_phone) == 10:
        clean_phone = ''.join(['(',clean_phone[:3],')',' ',clean_phone[3:6],'-' ,clean_phone[6:]])
    elif len(clean_phone) == 11 and clean_phone.startswith('1'):
        clean_phone = ''.join(['(',clean_phone[1:4],')',' ',clean_phone[4:7],'-',clean_phone[7:]])
    else:
        return None

    return clean_phone

# Cleans a list of phone numbers in 1 column
def clean_numbers_list(phone_list):
    clean_split = [y for y in [clean_phone_number(x) for x in phone_list.split(',')] if y is not None]
    if len(clean_split)>1:
        return ', '.join(clean_split)
    elif len(clean_split)==1:
        return clean_split[0]
    else:
        return None

def validate_phone(colname,PHONE):
    if PHONE is None or PHONE == 'None' or PHONE == np.nan:
        # If phone # is empty, intiliaze an empty DF
        phone_basic = pd.DataFrame(
            columns = ['PhoneNumber', 'ReportDate', 'LineType', 'PhoneCompany', 'PhoneLocation', 'FakeNumber', 'FakeNumberReason', 'ErrorCode', 'ErrorDescription'],
            index=[0]
        ).replace(np.nan,'')

    else:
        # If Phone is not empty, get just phone # (no hypen or parantheses)
        PHONE = re.sub('[\(\)\- ]','',PHONE)
        # API request
        resp = requests.get(f'https://api.phonevalidator.com/api/v3/phonesearch?apikey={APIKEY}&phone={PHONE}&type=basic',verify=False)
        # Get PhoneBasic info
        phone_basic = pd.DataFrame.from_dict(resp.json().get('PhoneBasic'),orient='index').T
    
    # Add column # corresponding to phone # column
    phone_basic.columns = [x+re.search('\d',colname)[0] for x in phone_basic.columns.to_list()]

    return phone_basic

#%%
file_path_old = 'old_data.csv'
file_path_new = 'new_data.csv'
# excel_path = 'cleaned_lead_list_' + re.search('\d{4}(-\d{2}){5}',file_path.name)[0] + '.xlsx'

data_old = pd.read_csv(file_path_old)
data = pd.read_csv(file_path_new)

data_copy = data.copy()

data_copy = (
    data_copy
    .merge(data_old[['Contact Full Name','Company Name']],how='outer',on=['Contact Full Name','Company Name'],indicator=True)
    .query('_merge == "left_only"')
    .drop(columns='_merge')
 )

#%%

# Strip string whitespace
data_copy = data_copy.astype(str).applymap(lambda x: x.strip())

# Remove Richmond, Charlottesville, and Henrico cities
cities_to_remove = ['Richmond', 'Charlottesville', 'Henrico']
data_copy = data_copy[(~data_copy['Company City'].isin(cities_to_remove))|(~data_copy['Contact City'].isin(cities_to_remove))]

### Data clean - phone #'s
# Define the phone number columns to process
phone_columns = data_copy.filter(regex='^Contact Phone \\d+$').columns.to_list()

# Apply phone formatting
data_copy[phone_columns] = data_copy[phone_columns].applymap(
    lambda x:
        clean_numbers_list(x) if ',' in x 
        else clean_phone_number(x) if x!='nan' 
        else None
    )

# Remove 804, 757, 540 area codes from all data
area_codes_to_remove = ['(804)', '(757)', '(540)']
data_copy = data_copy[~data_copy['Contact Phone 1'].str.startswith(tuple(area_codes_to_remove), na=False)]

# Function returns None for international numbers, so remove only international contacts with dropna
data_phone = data_copy.dropna(subset=phone_columns,how='all').reset_index(drop=True)
# Keep only first 3 phone cols
data_phone = data_phone[['First Name','Contact LI Profile URL'] + data_phone.filter(regex='Contact Phone [123](?!0)').columns.to_list()]

# Reformat Total AI columns from % to int
data_phone[data_phone.filter(like='AI').columns] = data_phone.filter(like='AI').applymap(lambda x: int(re.sub('%','',x)) if x!='nan' else 0)
# Only keep #s with AI>20
data_phone = data_phone[data_phone['Contact Phone 1 Total AI']>=20].reset_index(drop=True)
# Remove Contact 2 and 3 if AI<20
data_phone['Contact Phone 2'][data_phone['Contact Phone 2 Total AI'] < 20] = 'None'
data_phone['Contact Phone 3'][data_phone['Contact Phone 3 Total AI'] < 20] = 'None'

# Remove people with all invalid phone #s
data_phone = data_phone[
    ((data_phone.filter(regex='Contact Phone \d$') == 'None') | 
     data_phone.filter(regex='Contact Phone \d$').isna()).apply(lambda x: sum(x),axis=1) < 3
].reset_index(drop=True)

# Keep only phone # columns
data_phone = data_phone[['First Name','Contact LI Profile URL'] + phone_columns[:3]]
# Remove extensions
data_phone[phone_columns[:3]] = data_phone[phone_columns[:3]].applymap(lambda x: 'None' if 'x' in str(x) else x)


#%%

data_phone_val = pd.concat(
    [pd.concat([validate_phone(x,str(y)) for y in data_phone[x]]).reset_index(drop=True) 
     for x in data_phone.filter(like='Contact Phone')],
    axis=1).reset_index(drop=True)

data_phone = pd.concat([data_phone[['First Name','Contact LI Profile URL']],data_phone_val],axis=1)
data_phone[data_phone.filter(like='PhoneNumber').columns] = data_phone.filter(like='PhoneNumber').applymap(lambda x: '' if x=='' else clean_phone_number(x))

data_phone = data_phone[['First Name'] + data_phone.filter(like='PhoneNumber').columns.to_list() + [x for x in data_phone if x not in ['First Name'] + data_phone.filter(like='PhoneNumber').columns.to_list()] + ['Contact LI Profile URL']]


#%%

### Data clean - emails
email_columns = ['First Name','Company Name','Contact LI Profile URL','Primary Email'] + data_copy.filter(regex='^Email').columns.to_list()
# Keep email columns
data_email = data_copy[email_columns]


