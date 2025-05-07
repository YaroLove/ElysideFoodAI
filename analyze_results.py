import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns
from sklearn.metrics import r2_score
import os
from glob import glob
from datetime import datetime

def get_latest_results_file(results_dir):
    """Find the most recent results file in the specified directory."""
    files = glob(os.path.join(results_dir, 'estimation_openai_*.csv'))
    if not files:
        raise FileNotFoundError(f"No results files found in {results_dir}")
    return max(files, key=os.path.getctime)

def save_figure(fig, filename, dpi=300):
    fig.savefig(filename, dpi=dpi, bbox_inches='tight')
    plt.close(fig)

def analyze_model(data_path=None, output_dir='analysis_results'):
    os.makedirs(output_dir, exist_ok=True)
    
    # If no specific file is provided, use the latest one
    if data_path is None:
        data_path = get_latest_results_file('estimation_results')
    print(f"Analyzing results from: {data_path}")
    
    # Load and process data
    df = pd.read_csv(data_path)
    predictions = df['estimated_calories']
    true_values = df['actual_calories']
    
    # Calculate errors and metrics
    errors = predictions - true_values
    percentage_errors = (errors / true_values) * 100
    absolute_percentage_errors = np.abs(percentage_errors)
    
    # Analyze extreme cases
    sorted_indices = percentage_errors.sort_values(ascending=False).index
    n_extreme = 2
    
    print("\nWorst Overestimates:")
    for idx in sorted_indices[:n_extreme]:
        print(f"Image: {df['image'].iloc[idx]}, "
              f"True: {true_values.iloc[idx]:.0f} kcal, "
              f"Predicted: {predictions.iloc[idx]:.0f} kcal, "
              f"Error: +{percentage_errors.iloc[idx]:.1f}%")
        print(f"LLM Output: {df['llm_output'].iloc[idx]}\n")
    
    print("\nWorst Underestimates:")
    for idx in sorted_indices[-n_extreme:]:
        print(f"Image: {df['image'].iloc[idx]}, "
              f"True: {true_values.iloc[idx]:.0f} kcal, "
              f"Predicted: {predictions.iloc[idx]:.0f} kcal, "
              f"Error: {percentage_errors.iloc[idx]:.1f}%")
        print(f"LLM Output: {df['llm_output'].iloc[idx]}\n")
    
    # Simplified metrics calculation
    metrics = {
        'Mean_Error': np.mean(errors),
        'Mean_Percentage_Error': np.mean(percentage_errors),
        'Mean_Absolute_Percentage_Error': np.mean(absolute_percentage_errors),
    }
    
    error_percentiles = np.percentile(percentage_errors, [25, 50, 75])
    comprehensive_metrics = {'R-squared': r2_score(true_values, predictions)}
    
    # Simplified quartile calculation
    quartile_errors = {}
    quartiles = np.percentile(true_values, [25, 50, 75])
    ranges = ['Low', 'Low-Mid', 'Mid-High', 'High']
    
    for i, (lower, upper) in enumerate(zip([min(true_values), *quartiles], 
                                         [*quartiles, max(true_values)])):
        mask = (true_values >= lower) & (true_values < upper)
        quartile_errors[f"{ranges[i]} ({lower:.0f}-{upper:.0f} cal)"] = {
            'mean_error': np.mean(errors[mask])
        }
    
    # Create visualization with 3 subplots - adjusted figure size and layout
    fig = plt.figure(figsize=(20, 7))  # Wider figure, reduced height
    
    # Error distribution plot with mean error in legend
    ax1 = plt.subplot(1, 3, 1)
    sns.histplot(errors, kde=True, ax=ax1, bins=10)  # Added bins parameter for better distribution view
    plt.axvline(x=metrics['Mean_Error'], color='g', linestyle='-',
                label=f"Mean Error: {metrics['Mean_Error']:.1f} kcal")
    plt.title('Error Distribution', fontsize=12)
    plt.legend(fontsize=10)
    
    # Scatter plot - added equal aspect ratio and limits
    ax2 = plt.subplot(1, 3, 2)
    plt.scatter(true_values, predictions, alpha=0.5)
    plt.plot([min(true_values), max(true_values)],
             [min(true_values), max(true_values)],
             'r--')
    
    # Make the plot square and set equal limits
    min_val = min(min(true_values), min(predictions))
    max_val = max(max(true_values), max(predictions))
    plt.xlim(min_val, max_val)
    plt.ylim(min_val, max_val)
    ax2.set_aspect('equal')
    
    plt.xlabel('True Values', fontsize=11)
    plt.ylabel('Predictions', fontsize=11)
    plt.title('Predictions vs True Values', fontsize=12)
    
    # Metrics text - adjusted font size and spacing
    ax3 = plt.subplot(1, 3, 3)
    metrics_text = (
        f"Key Metrics:\n\n"  # Added extra newline for spacing
        f"R² = {comprehensive_metrics['R-squared']:.3f}\n"
        f"Mean Error = {metrics['Mean_Percentage_Error']:.1f}%\n"
        f"Median Error = {np.median(percentage_errors):.1f}%\n\n"  # Added extra newline
        f"Middle 50% of predictions fall between:\n"
        f"  {error_percentiles[0]:.1f}% and {error_percentiles[2]:.1f}%\n\n"
        f"Error by Range:\n"
    )
    
    for quartile, data in quartile_errors.items():
        metrics_text += f"{quartile}: {data['mean_error']:.1f} kcal\n"
    
    plt.text(0.1, 0.9, metrics_text, transform=ax3.transAxes,
             verticalalignment='top', fontfamily='monospace',
             fontsize=12)  # Reduced font size
    plt.axis('off')
    plt.title('Performance Metrics', fontsize=12)
    
    plt.tight_layout(w_pad=3)  # Added padding between subplots
    
    # Save results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    save_figure(fig, os.path.join(output_dir, f'detailed_analysis_{timestamp}.png'))
    
    # Print overall metrics
    print("\nOverall Performance Metrics:")
    print(f"R² Score: {comprehensive_metrics['R-squared']:.3f}")
    print(f"Mean Absolute Percentage Error: {metrics['Mean_Absolute_Percentage_Error']:.1f}%")
    print(f"Mean Error: {metrics['Mean_Error']:.1f} kcal")
    print(f"Median Error: {np.median(errors):.1f} kcal")

if __name__ == "__main__":
    analyze_model() 