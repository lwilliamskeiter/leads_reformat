import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO
import regex as re


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
    wkst_phone.set_column(1, data_phone.shape[1],
                          data_phone.drop(columns='First Name').applymap(lambda x: 0 if x is None else len(str(x))).max().max() + 10,
                          workbook.add_format({'font_size': 24}))

    # Set table style
    wkst_phone.add_table(0, 0, data_phone.shape[0], data_phone.shape[1]-1,
                        {'style': 'Table Style Medium 9',
                        'columns': [{'header': x} for x in data_phone]})

    # Rewrite headers with larger font size
    for col_num, value in enumerate(data_phone.columns.values):
        wkst_phone.write(0, col_num, value, workbook.add_format({'font_size': 14, 'bold': True}))
    # Change row height to 36
    for row in range(0,len(data_phone)-1):
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
        for row in range(data_email.shape[0]-1):
            wkst_email.write_url(row, col, '' if data_email.iloc[row,col]=='nan' else 'mailto:'+data_email.iloc[row,col],url_format)

    # Set email column widths
    for col in np.where(data_email.columns.str.contains('Primary Email|^Email \d+$',regex=True))[0]:
        wkst_email.set_column(col, col, 25, workbook.add_format({'font_size': 14}))

    # Change row height to 36
    for row in range(0,len(data_email)-1):
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

# Read file
file_path = st.file_uploader('Upload Contacts File',type=['csv'])
# file_path = 'MyContacts_export_flang@keitercpa.com_2023-12-07-13-28-26_raw.csv'  
if file_path is not None:
    excel_path = 'cleaned_lead_list_' + re.search('\d{4}(-\d{2}){5}',file_path.name)[0] + '.xlsx'

    data = pd.read_csv(file_path)
    data_copy = data.copy()

    # Strip string whitespace
    data_copy = data_copy.astype(str).applymap(lambda x: x.strip())

    # Remove Richmond, Charlottesville, and Henrico cities
    cities_to_remove = ['Richmond', 'Charlottesville', 'Henrico']
    data_copy = data_copy[(~data_copy['Company City'].isin(cities_to_remove))|(~data_copy['Contact City'].isin(cities_to_remove))]

    # Data clean - phone #'s
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

    # Keep only relevant columns for final data
    output_columns = ['First Name'] + phone_columns
    # Filter columns
    data_phone = data_phone[output_columns]


    # Data clean - emails
    email_columns = ['First Name','Company Name','Contact LI Profile URL','Primary Email'] + data_copy.filter(regex='^Email').columns.to_list()

    # Keep email columns
    data_email = data_copy[email_columns]



# print("Data processed and saved to", excel_path)

if file_path is not None:
    st.download_button(
        label="Download Formatted Excel Workbook",
        data=write_excel(data_phone,data_email),
        file_name=excel_path
    )
