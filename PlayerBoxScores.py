# -*- coding: utf-8 -*-
"""
Created on Sun Nov 27 21:43:50 2016

@author: DanLo1108
"""


from bs4 import BeautifulSoup
import numpy as np
import pandas as pd
import re
import string as st
import sqlalchemy as sa
import os
import yaml

from urllib.request import urlopen

#Break FG and FT down into integers
def get_made(x,var):
    x_var=x[var]
    try:
        return int(x_var[:x_var.index('-')])
    except:
        return np.nan
            
def get_attempts(x,var):
    x_var=x[var]
    try:
        return int(x_var[x_var.index('-')+1:])
    except:
        return np.nan
                
                
def append_boxscores(game_id,engine):

    url='http://www.espn.com/nba/boxscore?gameId='+str(game_id)
    
    
    page = urlopen(url)
    
    
    content=page.read()
    soup=BeautifulSoup(content,'lxml')
    
    
    tables=soup.find_all('table')
    
    results_head=[re.sub('\t|\n','',el.string) for el in tables[0].find_all('td')]        
    results_head_split=np.array_split(results_head,len(results_head)/5.)
            
    for ind in [1,2]:
        results=[el.string for el in tables[ind].find_all('td')]
        
        try:
            ind_stop=min([i for i in range(len(results)) if pd.notnull(results[i]) and ('DNP-' in results[i] or 'Did not play' in results[i])])-1
        except:
            ind_stop=min([i for i in range(len(results)) if pd.notnull(results[i]) and results[i] == 'TEAM'])
            
        ind_team=min([i for i in range(len(results)) if pd.notnull(results[i]) and results[i] == 'TEAM'])
            
        
        player_stats_df=pd.DataFrame(np.array_split(results[:ind_stop],ind_stop/15.),
                        columns=['Player','MP','FG','3PT','FT',
                                 'OREB','DREB','REB','AST','STL','BLK',
                                 'TOV','PF','PlusMinus','PTS'])
                                 
	for col in player_stats_df:
		try:
                	player_stats_df[col]=list(map(lambda x: float(x),player_stats_df[col]))
		except:
                	continue
            
        if ind_stop != ind_team:
            dnp_df=pd.DataFrame(np.array_split(results[ind_stop:ind_team],(ind_team-ind_stop)/2.),
                   columns=['Player','DNP_Reason'])
        else:
            dnp_df=pd.DataFrame(columns=['Player','DNP_Reason'])
                
        player_stats_df=player_stats_df.append(dnp_df).reset_index(drop=True)
        
        player_stats_df['Player']=[el.string for el in tables[ind].find_all('span')][0::3][:len(player_stats_df)]
	try:
            player_stats_df['PlayerID']=[el['href'][el['href'].find('id')+3:el['href'].find('id')+3+el['href'][el['href'].find('id')+3:].find('/')] for el in tables[ind].find_all('a',href=True)][:len(player_stats_df)]
        except:
            player_stats_df['PlayerID']=[el['href'][36:] for el in tables[ind].find_all('a',href=True)][:len(player_stats_df)]          
        #player_stats_df['PlayerAbbr']=[el['href'][36:][el['href'][36:].index('/')+1:] for el in tables[ind].find_all('a',href=True)][:len(player_stats_df)]      
        
	 try:
            player_stats_df['Position']=[el.string for el in tables[ind].find_all('span')][2::3][:len(player_stats_df)]
        except:
            spans=[el.string for el in tables[ind].find_all('span')]
            pos=[]
            for i in range(1,len(spans)):
                if spans[i] in ['PG','SG','SF','PF','C','G','F']:
                    pos.append(spans[i])
                elif spans[i-1] not in ['PG','SG','SF','PF','C','G','F'] and spans[i] not in ['PG','SG','SF','PF','C','G','F'] and spans[i] != spans[i-1]:
                    pos.append(None)
                
            if len(pos)==len(player_stats_df):
                player_stats_df['Position']=pos
            else:
                player_stats_df['Position']=pos+[None]
            
        player_stats_df=player_stats_df.replace('-----','0-0').replace('--',0)
        
        player_stats_df['Team']=results_head_split[ind-1][0]
        player_stats_df['GameID']=game_id
                
                
        player_stats_df['FGM']=player_stats_df.apply(lambda x: get_made(x,'FG'), axis=1)
        player_stats_df['FGA']=player_stats_df.apply(lambda x: get_attempts(x,'FG'), axis=1)
        
        player_stats_df['3PTM']=player_stats_df.apply(lambda x: get_made(x,'3PT'), axis=1)
        player_stats_df['3PTA']=player_stats_df.apply(lambda x: get_attempts(x,'3PT'), axis=1)
        
        player_stats_df['FTM']=player_stats_df.apply(lambda x: get_made(x,'FT'), axis=1)
        player_stats_df['FTA']=player_stats_df.apply(lambda x: get_attempts(x,'FT'), axis=1)
        
        player_stats_df['StarterFLG']=[1.0]*5+[0.0]*(len(player_stats_df)-5)
        
        column_order=['GameID','Player','PlayerID','Position','Team','StarterFLG','MP',
                      'FG','FGM','FGA','3PT','3PTM','3PTA','FT','FTM','FTA','OREB','DREB',
                      'REB','AST','STL','BLK','TOV','PF','PlusMinus','PTS','DNP_Reason']
        
        player_stats_df[column_order].to_sql('player_boxscores',
                                             con=engine,
                                             schema='nba',
                                             index=False,
                                             if_exists='append',
                                             dtype={'GameID': sa.types.INTEGER(),
                                                    'Player': sa.types.VARCHAR(length=255),
                                                    'PlayerID': sa.types.INTEGER(),
                                                    'Position': sa.types.CHAR(length=2),
                                                    'Team': sa.types.VARCHAR(length=255),
                                                    'StarterFLG': sa.types.BOOLEAN(),
                                                    'MP': sa.types.INTEGER(),
                                                    'FG': sa.types.VARCHAR(length=255),
                                                    'FGM': sa.types.INTEGER(),
                                                    'FGA': sa.types.INTEGER(),
                                                    '3PT': sa.types.VARCHAR(length=255),
                                                    '3PTM': sa.types.INTEGER(),
                                                    '3PTA': sa.types.INTEGER(),
                                                    'FT': sa.types.VARCHAR(length=255),
                                                    'FTM': sa.types.INTEGER(),
                                                    'FTA': sa.types.INTEGER(),
                                                    'OREB': sa.types.INTEGER(),
                                                    'DREB': sa.types.INTEGER(),
                                                    'REB': sa.types.INTEGER(),
                                                    'AST': sa.types.INTEGER(),
                                                    'STL': sa.types.INTEGER(),
                                                    'BLK': sa.types.INTEGER(),
                                                    'TOV': sa.types.INTEGER(),
                                                    'PF': sa.types.INTEGER(),
                                                    'PlusMinus': sa.types.INTEGER(),
                                                    'PTS': sa.types.INTEGER(),
                                                    'DNP_Reason': sa.types.VARCHAR(length=255)})    


def get_engine():
    #Get credentials stored in sql.yaml file (saved in root directory)
    if os.path.isfile('/sql.yaml'):
        with open("/sql.yaml", 'r') as stream:
            data_loaded = yaml.load(stream)
            
            #domain=data_loaded['SQL_DEV']['domain']
            user=data_loaded['BBALL_STATS']['user']
            password=data_loaded['BBALL_STATS']['password']
            endpoint=data_loaded['BBALL_STATS']['endpoint']
            port=data_loaded['BBALL_STATS']['port']
            database=data_loaded['BBALL_STATS']['database']
            
    db_string = "postgres://{0}:{1}@{2}:{3}/{4}".format(user,password,endpoint,port,database)
    engine=sa.create_engine(db_string)
    
    return engine


def get_gameids(engine):
    
    game_id_query='''
    select distinct
        gs."Season"
        ,gs."GameID"
    from
        nba.game_summaries gs
    left join
        nba.player_boxscores p on gs."GameID"=p."GameID" 
    where
        p."GameID" is Null
        and gs."Status"='Final'
        and gs."Season"=(select max("Season") from nba.game_summaries)
    order by
        gs."Season"
    '''
    
    game_ids=pd.read_sql(game_id_query,engine)
    
    return game_ids.GameID.tolist()


def update_player_boxscores(engine,game_id_list):
    cnt=0
    bad_gameids=[]
    for game_id in game_id_list:
        
        if np.mod(cnt,2000)==0:
            print('CHECK: ',cnt,len(bad_gameids))
    
        try:
            append_boxscores(game_id,engine)
            cnt+=1
            if np.mod(cnt,100)==0:
                print(str(round(float(cnt*100.0/len(game_ids)),2))+'%')
            
        except:
            bad_gameids.append(game_id)
            cnt+=1
            if np.mod(cnt,100) == 0:
                print(str(round(float(cnt*100.0/len(game_ids)),2))+'%')
            continue
        
        
def main():
    engine=get_engine()
    game_ids=get_gameids(engine)
    update_player_boxscores(engine,game_ids)
    
    
    
if __name__ == "__main__":
    main()


