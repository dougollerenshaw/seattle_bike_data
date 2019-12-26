import pandas as pd
import seaborn as sns
import calendar
import datetime
import os
from sodapy import Socrata
import plotly.graph_objects as go

from . import plotting_functions as pf


class BikeData(object):

    def __init__(self, location):

        self.location = location

        self._variable_names = {
            'spokane street bridge': {
                'total_column': 'spokane_st_bridge_total',
                'shortname': 'spokane',
                'data_address': 'upms-nr8w',
            },
            'fremont bridge': {
                'total_column': 'fremont_bridge',
                'shortname': 'fremont',
                'data_address': '65db-xm6k',
            },
            'second avenue cycletrack': {
                'total_column': '_2nd_ave_cycletrack',
                'shortname': 'second_ave',
                'data_address': 'avwm-i8ym',
            },
        }

        # get total counts at various levels of granularity
        self.hourly_totals = self._get_hourly_totals()
        self.daily_totals = self._get_daily_totals()
        self.grouped_by_weekday = self._group_by_weekday()
        self.grouped_by_month = self._group_by_month()
        self.rolling_yearly_sum = self._make_rolling_yearly()

        # define palettes
        self.weekday_palette = sns.color_palette("viridis", 7)
        self.monthly_palette = sns.color_palette("cividis", 12)
        self.yearly_palette = sns.color_palette(
            "Dark2", datetime.datetime.now().year - 2012 + 1)
        years = range(2012, datetime.datetime.now().year+1)
        self.yearly_palette_dict = {
            year: color for year, color in zip(years, self.yearly_palette)}

    def _get_hourly_totals(self):
        '''
        try getting data from local cache first
        then get data from server
        '''

        hourly_totals = self._data_from_cache()
        if hourly_totals is None:
            hourly_totals = self._data_from_server()

            # make cache directory and save hourly totals
            if os.path.exists('.bike_data_cache') == False:
                print('making dir')
                os.mkdir('.bike_data_cache')

            shortname = self._variable_names[self.location]['shortname']
            cache_filename = '{}_hourly_counts_cache.h5'.format(shortname)
            hourly_totals.to_hdf(
                os.path.join('.bike_data_cache', cache_filename),
                key='daily_totals'
            )

        return hourly_totals

    def _data_from_cache(self):
        '''
        try getting data from cache
        return None if data doesn't exist or if data is out of date
        '''
        shortname = self._variable_names[self.location]['shortname']
        cache_filename = '{}_hourly_counts_cache.h5'.format(shortname)

        if os.path.exists('.bike_data_cache') and cache_filename in os.listdir('.bike_data_cache'):
            hourly_totals = pd.read_hdf(
                os.path.join('.bike_data_cache', cache_filename),
                key='daily_totals'
            )
            # keep track of column names containing counts
            self._total_cols = [
                c for c in hourly_totals.columns[:4] if c != 'date']

            # return None if:
            # * cached data is more than 1 month old
            # * or cached data is not from current year
            # * or cached data is more than 25 days out of date
            if datetime.datetime.now().month - (hourly_totals['date'].max().month) > 1 or \
                    datetime.datetime.now().year != (hourly_totals['date'].max().year) or \
                    (datetime.datetime.now() - hourly_totals['date'].max()).days > 25:
                return None
            else:
                return hourly_totals.drop_duplicates()
        else:
            return None

    def _data_from_server(self):
        '''
        get crossings from data.seattle.gov

        they are delivered in an hourly format
        '''

        # connect to client
        client = Socrata("data.seattle.gov", None)

        # get data
        results = client.get(
            self._variable_names[self.location]['data_address'], limit=500000)

        # convert the result to a dataframe
        hourly_totals = (pd.DataFrame.from_records(results)
                         .rename(columns={self._variable_names[self.location]['total_column']: 'total'})
                         .fillna(0)
                         )

        # convert the 'date' column to a datetime
        hourly_totals['date'] = pd.to_datetime(hourly_totals['date'])

        # convert every other column to integers
        self._total_cols = [c for c in hourly_totals.columns if c != 'date']
        for col in self._total_cols:
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

        return hourly_totals.drop_duplicates()

    def _get_daily_totals(self):
        '''
        get daily totals from hourly totals
        '''
        daily_totals = self.hourly_totals.groupby(
            ['year', 'dayofyear']
        )[self._total_cols].sum()
        # in order for the merge to work, there needs to be a single matching hour index. Make it zero
        daily_totals['hour'] = 0
        daily_totals.set_index(['hour'], append=True, inplace=True)
        daily_totals = daily_totals.merge(
            self.hourly_totals[['weekday', 'day_name', 'day',
                                'date', 'month', 'dayofyear_float']],
            left_index=True,
            right_index=True,
            how='left'
        )

        # fix days with broken counter for spokane st bridge
        if self.location == 'spokane street bridge':
            daily_totals = self._fix_days_with_broken_counter(daily_totals)

        return daily_totals

    def _fix_days_with_broken_counter(self, daily_totals):
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

    def _group_by_weekday(self):
        '''
        group by day of week for each year
        '''
        day_totals = self.daily_totals
        grouped_by_weekday = day_totals.groupby(
            ['weekday', 'year'])[['total']].mean().rename(columns={'total': 'total_crossings_mean'}
                                                          )
        grouped_by_weekday['day_name'] = (grouped_by_weekday
                                          .index.get_level_values(0)
                                          .map(lambda x: calendar.day_name[x])
                                          )
        grouped_by_weekday = grouped_by_weekday.merge(
            (day_totals
                .groupby(['weekday', 'year'])[['total']]
                .std()
                .rename(columns={'total': 'total_crossings_std'})
             ),
            left_index=True,
            right_index=True
        )

        return grouped_by_weekday

    def _group_by_month(self):
        '''
        group by month for each year
        '''
        day_totals = self.daily_totals
        grouped_by_month = day_totals.groupby(
            ['month', 'year'])[['total']].sum().rename(columns={'total': 'total_crossings'}
                                                       )
        grouped_by_month = grouped_by_month.merge(
            day_totals.groupby(
                ['month', 'year'])[['total']].mean().rename(columns={'total': 'total_crossings_mean'}
                                                            ),
            left_index=True,
            right_index=True
        )
        grouped_by_month['month_name'] = grouped_by_month.index.get_level_values(
            0).map(lambda x: calendar.month_name[x])

        return grouped_by_month

    def _make_rolling_yearly(self):

        rolling_yearly_sum = self.daily_totals[[
            'total']].rolling(window=365).sum()

        rolling_yearly_sum = rolling_yearly_sum.merge(
            self.daily_totals[['weekday', 'day_name', 'day', 'date', 'month']],
            left_index=True,
            right_index=True
        )

        return rolling_yearly_sum

    def make_weekday_plot(self):
        '''
        plot one bar per weekday in each year
        '''
        years = sorted(self.grouped_by_weekday.reset_index()['year'].unique())
        self.weekday_plot = pf.make_weekday_plot_matplotlib(
            self.grouped_by_weekday,
            palette=[self.yearly_palette_dict[year] for year in years]
        )

    def make_monthly_plot(self, groupby='month'):
        '''
        plot one bar per month in each year

        input:
            groupby = 'month' or 'year'
        '''
        if groupby == 'month':
            years = sorted(self.grouped_by_weekday.reset_index()
                           ['year'].unique())
            palette = [self.yearly_palette_dict[year] for year in years]
        elif groupby == 'year':
            palette = self.monthly_palette

        self.monthly_plot = pf.make_monthly_plot_matplotlib(
            self.grouped_by_month,
            palette=palette,
            groupby=groupby,
        )

    def make_rolling_yearly_plot(self):
        '''
        plot rolling sum over past year
        '''
        self.rolling_yearly_plot = pf.make_rolling_yearly_plot_matplotlib(
            self.rolling_yearly_sum
        )
