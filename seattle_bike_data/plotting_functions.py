import seaborn as sns
import matplotlib.pyplot as plt
import calendar
import plotly.graph_objects as go


def make_weekday_plot_matplotlib(df, palette=None):

    f = sns.catplot(
        x='weekday',
        y='total_crossings_mean',
        data=df.reset_index(),
        kind='bar',
        hue='year',
        palette=palette,
        legend=False
    )
    f.ax.set_xticklabels([calendar.day_name[d]
                          for d in range(7)], rotation=45, ha='right')
    f.ax.legend(loc='best')
    f.ax.set_ylabel('Average crossings')
    f.fig.set_size_inches(12, 5)
    sns.despine()
    f.fig.tight_layout()

    return f

def make_monthly_plot_matplotlib(df, palette=None, groupby='year'):
    if groupby == 'month':
        f = sns.catplot(
            x='month',
            y='total_crossings',
            data=df.reset_index(),
            kind='bar',
            hue='year',
            palette=palette,
            legend=False
        )
        f.ax.set_xticklabels([calendar.month_name[d] for d in range(1,13)],rotation=45,ha='right')


    elif groupby == 'year':
        f = sns.catplot(
            x='year',
            y='total_crossings',
            data=df.reset_index(),
            kind='bar',
            hue='month',
            palette=palette,
            legend=False
        )
        
    f.ax.legend(loc='best')
    f.ax.set_ylabel('Total crossings')
    f.fig.set_size_inches(12,5)
    f.fig.tight_layout()
    sns.despine()

    return f

def make_rolling_yearly_plot_matplotlib(df):
    fig,ax=plt.subplots(figsize=(12,5))
    ax.plot(df['date'],df['total'],linewidth=3,color='black')
    ax.set_xlabel('date')
    ax.set_ylabel('sum over past 365 days')
    ax.set_title('rolling yearly total crossings')
    sns.despine()
    fig.tight_layout()
    return fig