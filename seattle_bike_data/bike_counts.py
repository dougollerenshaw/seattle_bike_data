import pandas as pd
from sodapy import Socrata


class BikeData(object):

    def __init__(self, location):

        self.location = location

        self.crossings = self.get_crossings()

    def get_crossings(self):
        '''
        get crossings from data.seattle.gov
        '''
        # rename the various total columns to 'total'
        total_translator = {
            'spokane street bridge': 'spokane_st_bridge_total'
        }

        # the address strings for the various counters
        data_addresses = {
            'spokane street bridge': 'upms-nr8w'
        }

        # connect to client
        client = Socrata("data.seattle.gov", None)

        # get data
        if self.location.lower() == 'spokane street bridge':
            results = client.get(data_addresses[self.location], limit=500000)

        # convert the result to a dataframe
        hourly_totals = (pd.DataFrame.from_records(results)
                         .rename(columns={total_translator[self.location]: 'total'})
                         .fillna(0)
                         )

        # convert the 'date' column to a datetime
        hourly_totals['date'] = pd.to_datetime(hourly_totals['date'])

        # convert every other column to integers
        total_cols = [c for c in hourly_totals.columns if c != 'date']
        for col in total_cols:
            hourly_totals[col] = hourly_totals[col].astype(int)

        # Add columns for weekday, hour, month, day of week and day of year
        hourly_totals['year'] = hourly_totals['date'].map(lambda x: x.year)
        hourly_totals['weekday'] = hourly_totals['date'].map(
            lambda x: x.dayofweek)
        hourly_totals['hour'] = hourly_totals['date'].map(lambda x: x.hour)
        hourly_totals['month'] = hourly_totals['date'].map(lambda x: x.month)
        hourly_totals['day'] = hourly_totals['date'].map(lambda x: x.day)
        hourly_totals['day_name'] = hourly_totals['date'].map(
            lambda x: x.day_name())
        hourly_totals['dayofyear'] = hourly_totals['date'].map(
            lambda x: x.dayofyear)

        def get_dayofyear_float(row):
            return row['dayofyear'] + row['hour']/24.0
        hourly_totals['dayofyear_float'] = hourly_totals.apply(
            get_dayofyear_float, axis=1)

        hourly_totals = hourly_totals.sort_values(by='date')
        hourly_totals.set_index(['year', 'dayofyear', 'hour'], inplace=True)

        # get day totals
        daily_totals = hourly_totals.groupby(['year', 'dayofyear'])[
            total_cols].sum()
        # in order for the merge to work, there needs to be a single matching hour index. Make it zero
        daily_totals['hour'] = 0
        daily_totals.set_index(['hour'], append=True, inplace=True)

        daily_totals = daily_totals.merge(
            hourly_totals[['weekday', 'day_name', 'day',
                           'date', 'month', 'dayofyear_float']],
            left_index=True,
            right_index=True,
            how='left'
        )

        # fix days with broken counter for spokane st bridge
        if self.location == 'spokane street bridge':
            daily_totals = self.fix_days_with_broken_counter(daily_totals)

        # make hourly and daily totals into attributes
        self.hourly_totals = hourly_totals
        self.daily_totals = daily_totals

    def fix_days_with_broken_counter(self, daily_totals):
        '''
        copper thieves took down the Spokane St counter twice in late 2018/early 2019 
        (https://westseattlebikeconnections.org/2019/01/03/actual-bike-counts-up-in-2018/). 
        Those days show up as days with counts of zero

        I'm going to replace those days with the median counts from all of the matching 
        weekdays on previous years (e.g., for a Monday in 2018, I'll find each of the 
        closest Mondays in previous years, then take the medians of those counts). 
        '''

        def find_nearest_matching_day(df_in, day_of_year, weekday, year):
            '''finds nearest matching weekday in a given year'''
            df = df_in.reset_index()
            candidate_days = df[
                (df['weekday'] == weekday)
                & (df['year'] == year)
            ]
            # return the row with the matching weekday and the closest day of year
            return candidate_days[((candidate_days['dayofyear']-day_of_year).abs() == (candidate_days['dayofyear']-day_of_year).abs().min())]

        def get_all_previous_matching_days(row):
            '''finds nearest weekday matched entry for every previous year for a given row'''
            current_year = row.name[0]
            day_of_year = row.name[1]
            matches = []
            for year in [year for year in daily_totals.reset_index().year.unique() if year < current_year]:
                matches.append(
                    find_nearest_matching_day(
                        daily_totals, 
                        day_of_year, 
                        row['weekday'], 
                        year
                    )
                )
            return pd.concat(matches)

        days_the_thief_struck = daily_totals[daily_totals['total'] == 0]

        for idx, row in days_the_thief_struck.iterrows():
            matches = get_all_previous_matching_days(row)
            daily_totals.at[idx, 'total'] = int(
                matches[['total']].median().values)

        return daily_totals
