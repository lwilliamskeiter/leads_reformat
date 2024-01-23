import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO
import regex as re
import requests
import urllib3
from datetime import date

urllib3.disable_warnings()

APIKEY = '5ab4064c-e88a-40c0-9358-290709f22db0'
today = date.today()

#%% Functions
def clean_phone_number(phone):
    # Remove phone extension and non-numeric characters
    clean_phone = re.sub('^\+','',re.sub('[^0-9]','',re.split(' [a-z]+.+',phone)[0]))
    if pd.isna(clean_phone) or clean_phone.startswith(('800', '844', '888')) or len(clean_phone)>11:
        return None
    
    if len(clean_phone) == 10:
        clean_phone = ''.join(['(',clean_phone[:3],')',' ',clean_phone[3:6],'-' ,clean_phone[6:]])
    elif len(clean_phone) == 11 and clean_phone.startswith('1'):
        clean_phone = ''.join(['(',clean_phone[1:4],')',' ',clean_phone[4:7],'-',clean_phone[7:]])
    else:
        return None
    
    # If # has an extension, re include it
    if 'ext' in phone or bool(re.search('x\s?\d+',phone,flags=re.I)):
        clean_phone = clean_phone + ' ext. ' + re.sub('[^\d+$]','',re.search('(ext\.?|x?)\s?\d+$',phone,flags=re.I)[0])

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
        PHONE = re.sub('[\(\)\- ]','',PHONE)
        # API request
        resp = requests.get(f'https://api.phonevalidator.com/api/v3/phonesearch?apikey={APIKEY}&phone={PHONE}&type=basic',verify=False)
        # Get PhoneBasic info
        phone_basic = pd.DataFrame.from_dict(resp.json().get('PhoneBasic'),orient='index').T
    
    # Add column # corresponding to phone # column
    phone_basic.columns = [x+re.search('\d',colname)[0] for x in phone_basic.columns.to_list()]

    return phone_basic

# Write to excel
def write_excel(data_phone,data_email):
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
    for i in list(np.where([x in data_phone.filter(like='PhoneNumber').columns.to_list() for x in data_phone.columns.to_list()])[0]):
        wkst_phone.set_column(i,i,30,workbook.add_format({'font_size': 24}))
    # Set remaining column formats
    for j in [x for x in range(data_phone.shape[1]) if x not in [0] + list(np.where([x in data_phone.filter(like='PhoneNumber').columns.to_list() for x in data_phone.columns.to_list()])[0])]:
        wkst_phone.set_column(j,j,max([data_phone.iloc[:,j].dropna().apply(len).max(),14]))
    
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
    for col in np.where(data_email.columns.str.contains('Primary Email|^Email \d+$',regex=True))[0]:
        for row in range(data_email.shape[0]):
            wkst_email.write_url(row, col, '' if data_email.iloc[row,col]=='nan' else 'mailto:'+data_email.iloc[row,col],url_format)

    # Set email column widths
    for col in np.where(data_email.columns.str.contains('Primary Email|^Email \d+$',regex=True))[0]:
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
file_path = st.file_uploader('Upload New Contacts File',type=['csv'])
on = st.toggle('Add Old Contacts File')
if on:
    file_path_old = st.file_uploader('Upload Old Contacts File',type=['csv'])

if file_path is not None:
    if on and file_path_old is not None:
        st.button('Reformat leads!',key='button',on_click=click_button)
    else:
        st.button('Reformat leads!',key='button',on_click=click_button)

if file_path is not None:
    excel_path = 'cleaned_' + re.sub('\.csv','',file_path.name) + '_' + today.strftime("%y") + '_' + today.strftime("%m") + '_' + today.strftime("%d") + '.xlsx'
    
    if st.session_state.clicked:

        data = pd.read_csv(file_path)
        data_copy = data.copy()

        # If old file provided
        if on:
            if file_path_old is not None:
                data_old = pd.read_csv(file_path_old)
                data_copy = (
                    data_copy
                    .merge(data_old[['Contact Full Name','Company Name']],how='outer',on=['Contact Full Name','Company Name'],indicator=True)
                    .query('_merge == "left_only"')
                    .drop(columns='_merge')
                    .reset_index(drop=True)
                )
            else:
                st.warning('You need to upload your old contacts file!')
            
        with st.spinner():

            # Strip string whitespace
            data_copy = data_copy.astype(str).applymap(lambda x: x.strip())

            # Remove Richmond, Charlottesville, and Henrico cities
            cities_to_remove = ['Richmond', 'Charlottesville', 'Henrico']
            data_copy = data_copy[(~data_copy['Company City'].isin(cities_to_remove))|(~data_copy['Contact City'].isin(cities_to_remove))].reset_index(drop=True)

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
            data_copy = data_copy[~data_copy['Contact Phone 1'].str.startswith(tuple(area_codes_to_remove), na=False)].reset_index(drop=True)

            # Function returns None for international numbers, so remove only international contacts with dropna
            data_phone = data_copy.dropna(subset=phone_columns,how='all').reset_index(drop=True)
            # Keep only first 3 phone cols
            data_phone = data_phone[
                ['First Name','Contact LI Profile URL','Contact State','Company State'] + 
                data_phone.filter(regex='Contact Phone [123](?!0)').columns.to_list()
            ]

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
            data_phone = data_phone[['First Name','Contact LI Profile URL','Contact State','Company State'] + phone_columns[:3]]
            # Remove extensions
            data_phone[phone_columns[:3]] = data_phone[phone_columns[:3]].applymap(lambda x: 'None' if 'x' in str(x) else x)
            
            # Validate phone #s
            data_phone_val = pd.concat(
                [pd.concat([validate_phone(x,str(y)) for y in data_phone[x]]).reset_index(drop=True) 
                for x in data_phone.filter(like='Contact Phone')],
            axis=1).reset_index(drop=True)
            
            # Join names to numbers
            data_phone = pd.concat([data_phone[['First Name','Contact LI Profile URL','Contact State','Company State']],data_phone_val],axis=1)
            # Reformat phone #s
            data_phone[data_phone.filter(like='PhoneNumber').columns] = data_phone.filter(like='PhoneNumber').applymap(lambda x: '' if x=='' else clean_phone_number(x))
            # Reorder columns
            data_phone = data_phone[
                ['First Name'] + 
                data_phone.filter(like='PhoneNumber').columns.to_list() + 
                ['Contact State','Company State'] +
                [x for x in data_phone if x not in 
                 ['First Name','Contact LI Profile URL','Contact State','Company State'] + data_phone.filter(like='PhoneNumber').columns.to_list()] + 
                ['Contact LI Profile URL']
            ]

            ### Data clean - emails
            email_columns = ['First Name','Company Name','Contact LI Profile URL','Primary Email'] + data_copy.filter(regex='^Email').columns.to_list()
            # Keep email columns
            data_email = data_copy[email_columns].reset_index(drop=True)
        
        
        if on:
            if file_path_old is not None:
                st.download_button(
                    label="Download Formatted Excel Workbook",
                    data=write_excel(data_phone,data_email),
                    file_name=excel_path,
                    type='primary'
                )
                st.button('Reset',on_click=reset_button)
        else:
            st.download_button(
                label="Download Formatted Excel Workbook",
                data=write_excel(data_phone,data_email),
                file_name=excel_path,
                type='primary'
            )
            st.button('Reset',on_click=reset_button)

    # # Download button
    # if file_path is not None and st.session_state['button']:
        
