import seaborn as sns
import matplotlib.pyplot as pyplot
import calendar


def make_weekday_plot(df, palette=None):

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

def make_monthly_plot(df, palette=None):
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
    f.ax.legend(loc='best')
    f.ax.set_ylabel('Total crossings')
    f.fig.set_size_inches(12,5)
    f.fig.tight_layout()
    sns.despine()

    return f
