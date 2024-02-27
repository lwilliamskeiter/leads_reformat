import os
import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO
import regex as re
import requests
import urllib3
from datetime import date
from dotenv import load_dotenv
import pickle

load_dotenv()
urllib3.disable_warnings()

#%% Load global variables
APIKEY = os.getenv('APIKEY')
if len(APIKEY)==0:
    APIKEY = st.secrets['APIKEY']
today = date.today()

# Get requests pickle or initialize empty requests dict
if 'phone_requests.p' in os.listdir():
    phone_requests = pickle.load(open("phone_requests.p", "rb"))
else:
    phone_requests = {}

timezones = {
    'Alabama': '-6',
    'Alaska': '-9, -10',  # Includes Aleutian Islands
    'Arizona': '-7',      # Arizona does not observe Daylight Saving Time
    'Arkansas': '-6',
    'California': '-8',
    'Colorado': '-7',
    'Connecticut': '-5',
    'Delaware': '-5',
    'Florida': '-5, -6',  # Western parts are in Central Time
    'Georgia': '-5',
    'Hawaii': '-10',
    'Idaho': '-7, -8',    # Northern Idaho is in Pacific Time
    'Illinois': '-6',
    'Indiana': '-5, -6',  # Northwestern and southwestern parts are in Central Time
    'Iowa': '-6',
    'Kansas': '-6, -7',   # Western Kansas is in Mountain Time
    'Kentucky': '-5, -6', # Western parts are in Central Time
    'Louisiana': '-6',
    'Maine': '-5',
    'Maryland': '-5',
    'Massachusetts': '-5',
    'Michigan': '-5, -6', # Western part of the Upper Peninsula is in Central Time
    'Minnesota': '-6',
    'Mississippi': '-6',
    'Missouri': '-6',
    'Montana': '-7',
    'Nebraska': '-6, -7', # Western Nebraska is in Mountain Time
    'Nevada': '-8, -7',   # Small part of eastern Nevada is in Mountain Time
    'New Hampshire': '-5',
    'New Jersey': '-5',
    'New Mexico': '-7',
    'New York': '-5',
    'North Carolina': '-5',
    'North Dakota': '-6, -7', # Southwestern part is in Mountain Time
    'Ohio': '-5',
    'Oklahoma': '-6',
    'Oregon': '-8, -7',       # Small part of eastern Oregon is in Mountain Time
    'Pennsylvania': '-5',
    'Rhode Island': '-5',
    'South Carolina': '-5',
    'South Dakota': '-6, -7', # Western South Dakota is in Mountain Time
    'Tennessee': '-5, -6',    # Eastern part is in Eastern Time, rest is in Central
    'Texas': '-6, -7',        # Western tip is in Mountain Time
    'Utah': '-7',
    'Vermont': '-5',
    'Virginia': '-5',
    'Washington': '-8',
    'West Virginia': '-5',
    'Wisconsin': '-6',
    'Wyoming': '-7'
}

#%% Functions
def clean_phone_number(phone):
    # Remove phone extension and non-numeric characters
    clean_phone = re.sub('^\+','',re.sub('[^0-9]','',re.split(' [a-z]+.+',phone)[0]))
    # If # is empty, too long (international), spamlike, or has an extension
    if clean_phone in ['','nan','None'] or len(clean_phone)>11 or clean_phone.startswith(('800', '844', '888')) or bool(re.search('x\s?\d+',phone,flags=re.I)) or 'ext' in clean_phone:
        return None
    elif len(clean_phone) == 10:
        return clean_phone
    elif len(clean_phone) == 11 and clean_phone.startswith('1'):
        return clean_phone[1:]
    else:
        return None

def format_phone_number(phone):
    if phone not in ['','nan','None',None]:
        return ''.join(['(', phone[:3], ') ', phone[3:6], '-', phone[6:]])
    else:
        return None

# Cleans a list of phone numbers in 1 column
def clean_numbers_list(phone_list):
    clean_split = [y for y in [clean_phone_number(x) for x in phone_list.split(',')] if y is not None]
    if len(clean_split)>1:
        return ', '.join(clean_split)
    elif len(clean_split)==1:
        return clean_split[0]
    else:
        return None

# Validate phone numbers

def validate_phone(colname,PHONE):
    if PHONE is None or PHONE == 'None' or PHONE == np.nan:
        # If phone # is empty, intiliaze an empty DF
        phone_basic = pd.DataFrame(
            columns = ['PhoneNumber', 'ReportDate', 'LineType', 'PhoneCompany', 'PhoneLocation', 'FakeNumber', 'FakeNumberReason', 'ErrorCode', 'ErrorDescription'],
            index=[0]
        ).replace(np.nan,'')

    else:
        # If Phone is not empty, get just phone # (no hypen or parantheses)
        if bool(re.search('[^0-9]',PHONE)):
            PHONE = re.sub('[\(\)\- ]','',PHONE)
        # API request
        resp = requests.get(f'https://api.phonevalidator.com/api/v3/phonesearch?apikey={APIKEY}&phone={PHONE}&type=basic',verify=False)
        # Get PhoneBasic info
        phone_basic = pd.DataFrame.from_dict(resp.json().get('PhoneBasic'),orient='index').T
    
    # Add column # corresponding to phone # column
    phone_basic.columns = [x+re.search('\d',colname)[0] if bool(re.search('\d',colname)) 
                           else x+str(np.where([x in colname for x in phone_columns])[0][0]+1)
                           for x in phone_basic.columns.to_list()]

    return phone_basic

# Write to excel
def write_excel(data_phone,data_email,phone_cols):
    output = BytesIO()
    writer = pd.ExcelWriter(output, engine="xlsxwriter")

    # Convert the dataframes to an XlsxWriter Excel object.
    data_phone.to_excel(writer, sheet_name="Phone", index=False)
    data_email.to_excel(writer, sheet_name="Email", index=False)

    # Get the xlsxwriter workbook and worksheet objects.
    workbook = writer.book
    wkst_phone = writer.sheets["Phone"]
    wkst_email = writer.sheets["Email"]

    ### Set Phone sheet format
    # Set column font sizes and widths
    wkst_phone.set_column(0, 0, max([data_phone['First Name'].apply(len).max(),14]), workbook.add_format({'font_size': 14}))
    # Set phone # column format
    for i in list(np.where([x in phone_cols for x in data_phone.columns.to_list()])[0]):
        wkst_phone.set_column(i,i,30,workbook.add_format({'font_size': 24}))
    # Set remaining column formats
    for j in [x for x in range(data_phone.shape[1]) if x not in [0] + list(np.where([x in phone_cols for x in data_phone.columns.to_list()])[0])]:
        wkst_phone.set_column(j,j,max([data_phone.iloc[:,j].dropna().apply(len).max(),len(data_phone.iloc[:,j].name)+5,14]))
    
    for k in np.where([x in 'Timezone' for x in data_phone.columns.to_list()])[0]:
        wkst_phone.set_column(k,k,max([data_phone.iloc[:,k].dropna().apply(len).max(),13]))
    
    # Set table style
    wkst_phone.add_table(0, 0, data_phone.shape[0], data_phone.shape[1]-1,
                        {'style': 'Table Style Medium 9',
                        'columns': [{'header': x} for x in data_phone]})

    # Rewrite headers with larger font size
    for col_num, value in enumerate(data_phone.columns.values):
        wkst_phone.write(0, col_num, value, workbook.add_format({'font_size': 14, 'bold': True}))
    # Change row height to 36
    for row in range(0,data_phone.shape[0]+1):
        wkst_phone.set_row(row,36)

    ### Set Email sheet format
    # Set column font sizes and widths
    wkst_email.set_column(0, 0, max([data_email['First Name'].apply(len).max(),14]), workbook.add_format({'font_size': 14}))
    wkst_email.set_column(3, data_email.shape[1], max([data_email['First Name'].apply(len).max(),14]), workbook.add_format({'font_size': 14}))
    wkst_email.set_column(1, 2, 25, workbook.add_format({'font_size': 14}))

    # Set emails to hyperlinks
    # Set format
    url_format = workbook.get_default_url_format()
    url_format.font_size = 14
    # Apply to email addresses
    for col in np.where(data_email.columns.str.contains('Primary Email|^Email \d+$|Email Address',regex=True))[0]:
        for row in range(data_email.shape[0]):
            wkst_email.write_url(row, col, '' if data_email.iloc[row,col]=='nan' else 'mailto:'+data_email.iloc[row,col],url_format)

    # Set email column widths
    for col in np.where(data_email.columns.str.contains('Primary Email|^Email \d+$|Email Address',regex=True))[0]:
        wkst_email.set_column(col, col, 25, workbook.add_format({'font_size': 14}))

    # Change row height to 36
    for row in range(0,data_email.shape[0]+1):
        wkst_email.set_row(row,36)

    # Set table style
    wkst_email.add_table(0, 0, data_email.shape[0], data_email.shape[1]-1,
                        {'style': 'Table Style Medium 9',
                        'columns': [{'header': x} for x in data_email]})

    ### Close file write
    writer.close()

    processed_data = output.getvalue()
    return processed_data


#%% APP
st.set_page_config(
     page_title='Leads File Reformat',
    #  layout="wide",
)

def click_button():
    st.session_state.clicked = True

def reset_button():
    st.session_state.clicked = False

if 'clicked' not in st.session_state:
    st.session_state.clicked = False

# Read file(s)
contact_source = st.write('App supports: ZoomInfo, Seamless')
validate = st.toggle('Use Phone Validation API')
file_path = st.file_uploader('Upload New Contacts File',key='new_data_upload',type=['csv'])
on = st.toggle('Add Old Contacts File')
if on:
    file_path_old = st.file_uploader('Upload Old Contacts File',key='old_data_upload',type=['csv'])

if file_path is not None:
    if on:
        if file_path_old is not None:
            st.button('Reformat leads!',on_click=click_button)
    else:
        st.button('Reformat leads!',on_click=click_button)

if file_path is not None:
    excel_path = 'cleaned_' + re.sub('\.csv','',file_path.name) + '_' + today.strftime("%y") + '_' + today.strftime("%m") + '_' + today.strftime("%d") + '.xlsx'

    if st.session_state.clicked:

        # Read in files
        data = pd.read_csv(file_path)
        data_copy = data.copy()
        # Keep only US contacts
        data_copy = data_copy[data_copy.filter(like='Country').isin(['US','USA','United States']).any(axis=1)]

        # If old file provided
        if on:
            if file_path_old is not None:
                data_old = pd.read_csv(file_path_old)
                if 'Contact Full Name' not in data.columns:
                    data_copy['Contact Full Name'] = data_copy[['First Name','Last Name']].apply(lambda x: ' '.join(x), axis=1)
                    data_old['Contact Full Name'] = data_old[['First Name','Last Name']].apply(lambda x: ' '.join(x), axis=1)
                
                data_copy = (
                    data_copy
                    .merge(data_old[['Contact Full Name','Company Name']],how='outer',on=['Contact Full Name','Company Name'],indicator=True)
                    .query('_merge == "left_only"').drop(columns='_merge') # Keep only unique contacts
                    .reset_index(drop=True)
                )
            else:
                st.warning('You need to upload your old contacts file!')
            
        # Coerce data to str and strip string whitespace
        data_copy = data_copy.applymap(lambda x: str(x).strip())

        # Remove Richmond, Charlottesville, and Henrico cities
        cities_to_remove = ['Richmond', 'Charlottesville', 'Henrico']
        data_copy = data_copy[~data_copy.filter(like='City').isin(cities_to_remove).any(axis=1)].reset_index(drop=True)
        
        # Define the phone number columns to process - Keep only first 3 phone cols if >3
        phone_columns = data_copy.drop(columns=data_copy.filter(regex='Company|AI').columns).filter(regex='[Pp]hone')
        if all([bool(re.search('(\d+)$',x)) for x in phone_columns]):
            phone_columns = phone_columns.filter(regex=' [123]$').columns.to_list()
        else:
            phone_columns = phone_columns.columns.to_list()

        # Remove 804, 757, 540 area codes from all data
        area_codes_to_remove = ['(804)', '(757)', '(540)']
        data_copy = data_copy[~data_copy[phone_columns[0]].str.startswith(tuple(area_codes_to_remove), na=False)].reset_index(drop=True)
        
        with st.spinner():
            ### Data clean
            # Get non-phone columns to keep
            other_cols = ['First Name',data_copy.filter(regex='^(LinkedIn )?Contact( LI)? Profile URL').columns[0]] + data_copy.filter(regex='State$').columns.to_list()
            
            # Keep only relevant phone/phone AI columns and remove only international contacts with dropna
            data_phone = (
                data_copy[other_cols + data_copy.drop(columns=data_copy.filter(regex='Company').columns).filter(regex='[Pp]hone').columns.to_list()]
                .dropna(subset=phone_columns,how='all').reset_index(drop=True)
            )
            
            # Apply phone formatting
            data_phone[phone_columns] = data_phone[phone_columns].applymap(lambda x: clean_numbers_list(str(x)))
            
            # Reformat Total AI columns from % to int
            if not data_copy.filter(like=' AI').columns.empty:
                data_phone[data_phone.filter(like='AI').columns] = data_phone.filter(like='AI').applymap(lambda x: int(re.sub('%','',str(x))) if str(x)!='nan' else 0)

                # Only keep #s with AI>20
                data_phone = data_phone[data_phone['Contact Phone 1 Total AI']>=20].reset_index(drop=True)
                # Remove Contact Phone 2 and 3 if AI<20
                data_phone.loc[data_phone['Contact Phone 2 Total AI'] < 20, 'Contact Phone 2'] = 'None'
                data_phone.loc[data_phone['Contact Phone 3 Total AI'] < 20, 'Contact Phone 3'] = 'None'

            # Keep only phone # columns
            data_phone = data_phone[other_cols + phone_columns]
            # Remove people with all invalid phone #s
            data_phone = (data_phone[
                ((data_phone[phone_columns].isin(['nan','None'])) | 
                 data_phone[phone_columns].isna()).apply(sum,axis=1) < len(phone_columns)
            ].reset_index(drop=True))

            if validate:
                # Validate phone #s
                data_phone_val = pd.concat(
                    [pd.concat([validate_phone(x,str(y)) for y in data_phone[x]]).reset_index(drop=True) 
                    for x in phone_columns], axis=1
                ).reset_index(drop=True)
                # Rename phone number columns
                # data_phone_val = data_phone_val.rename(columns=dict(zip(data_phone_val.filter(regex='PhoneNumber').columns.to_list(),phone_columns)))
                # Join names to numbers
                data_phone = pd.concat([data_phone.drop(columns=phone_columns),data_phone_val],axis=1)
                final_phone_cols = data_phone.filter(regex='PhoneNumber').columns.to_list()
            else:
                final_phone_cols = phone_columns

            # Reformat phone #s
            data_phone[final_phone_cols] = data_phone[final_phone_cols].applymap(format_phone_number)
            # Add timezones
            data_phone['Timezone'] = data_phone.filter(like='State').applymap(timezones.get).apply(lambda x: [y for y in x.unique() if y is not None][0] if len([y for y in x.unique() if y is not None])>0 else '', axis=1)
            # Coerce to int and sort
            data_phone['Timezone'] = data_phone['Timezone'].astype(str).str.extractall('(-?\d+)').astype(int).reset_index().groupby('level_0').agg(lambda x: x.sort_values(ascending=False))[0]
            data_phone['Timezone'] = [re.sub('\[|\]','',', '.join([str(x)])) if len(x)>1 else x[0] if x != [] else '' for x in data_phone['Timezone'].map(lambda x: [int(y) for y in re.findall('-?\d+',str(x))])]
            # Reorder columns
            data_phone = data_phone[
                [other_cols[0]] + 
                final_phone_cols + 
                ['Timezone'] +
                other_cols[2:] +
                [x for x in data_phone if x not in other_cols + final_phone_cols + ['Timezone']] + 
                [other_cols[1]]
            ]

            ### Data clean - emails
            email_columns = email_columns = ['First Name','Company Name',
                 data_copy.filter(regex='^(LinkedIn )?Contact( LI)? Profile URL').columns[0],
                 data_copy.filter(regex='^(Primary )?Email( Address)?$').columns[0]] + data_copy.filter(regex='^Email \d+').columns.to_list()
            # Keep email columns
            data_email = data_copy[email_columns].astype(str).reset_index(drop=True)
        
        
        if on:
            if file_path_old is not None:
                st.download_button(
                    label="Download Formatted Excel Workbook",
                    data=write_excel(data_phone,data_email,final_phone_cols),
                    file_name=excel_path,
                    type='primary'
                )
                # st.button('Reset',on_click=reset_button)
        else:
            st.download_button(
                label="Download Formatted Excel Workbook",
                data=write_excel(data_phone,data_email,final_phone_cols),
                file_name=excel_path,
                type='primary'
            )
        st.button('Reset',on_click=reset_button)

