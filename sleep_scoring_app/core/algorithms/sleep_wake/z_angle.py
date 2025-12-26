"""
Z-angle calculation utilities for raw accelerometer data.

The z-angle represents the angle of the accelerometer (and thus the arm) relative
to the horizontal plane. It is calculated from tri-axial acceleration values.

This is a core component for van Hees (2015) SIB and HDCZA (2018) sleep detection
algorithms, which detect sustained inactivity by monitoring z-angle changes.

Mathematical Formula:
    z_angle = arctan(az / sqrt(ax^2 + ay^2)) * (180/pi)

Where:
    - ax, ay, az: Acceleration in g-units along X, Y, Z axes
    - Result: Angle in degrees

Physical Interpretation:
    - 0 deg: Arm horizontal
    - +90 deg: Arm pointing up (watch face down)
    - -90 deg: Arm pointing down (watch face up)

The z-angle is orientation-invariant when using changes/differences rather than
absolute values, which is why van Hees algorithms use z-angle differences.

References:
    van Hees VT, et al. (2015). A Novel, Open Access Method to Assess Sleep Duration
    Using a Wrist-Worn Accelerometer. PLoS ONE.
    https://doi.org/10.1371/journal.pone.0142533

    van Hees VT, et al. (2018). Estimating sleep parameters using an accelerometer
    without sleep diary. Scientific Reports.
    https://doi.org/10.1038/s41598-018-31266-z

"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def calculate_z_angle_from_arrays(
    ax: np.ndarray,
    ay: np.ndarray,
    az: np.ndarray,
    allow_nan: bool = True,
) -> np.ndarray:
    """
    Calculate z-angle from tri-axial acceleration arrays.

    The z-angle represents the angle of the arm relative to horizontal,
    calculated using the arctangent of the vertical acceleration component
    divided by the horizontal plane magnitude.

    Args:
        ax: X-axis acceleration in g-units
        ay: Y-axis acceleration in g-units
        az: Z-axis acceleration in g-units
        allow_nan: If True, NaN values propagate through calculation (for ISM handling).
                   If False, raises ValueError on NaN input. Default: True.

    Returns:
        Z-angle in degrees (same shape as input arrays). NaN inputs produce NaN outputs.

    Raises:
        ValueError: If arrays have different lengths, contain infinite values,
                    or contain NaN when allow_nan=False

    Example:
        >>> ax = np.array([0.1, 0.0, -0.1])
        >>> ay = np.array([0.2, 0.0, -0.2])
        >>> az = np.array([0.9, 1.0, 0.9])
        >>> z_angle = calculate_z_angle_from_arrays(ax, ay, az)
        >>> z_angle
        array([76.3, 90.0, 76.3])

    """
    # Validate inputs
    if not (len(ax) == len(ay) == len(az)):
        msg = f"All acceleration arrays must have the same length: ax={len(ax)}, ay={len(ay)}, az={len(az)}"
        raise ValueError(msg)

    if len(ax) == 0:
        msg = "Acceleration arrays cannot be empty"
        raise ValueError(msg)

    # Check for invalid values
    for name, arr in [("ax", ax), ("ay", ay), ("az", az)]:
        if not allow_nan and np.any(np.isnan(arr)):
            msg = f"{name} contains NaN values"
            raise ValueError(msg)
        if np.any(np.isinf(arr)):
            msg = f"{name} contains infinite values"
            raise ValueError(msg)

    # Calculate horizontal plane magnitude: sqrt(ax^2 + ay^2)
    # NaN values will propagate naturally through numpy operations
    horizontal_magnitude = np.sqrt(ax**2 + ay**2)

    # Calculate z-angle using arctangent: atan(az / horizontal_magnitude)
    # arctan2 is more numerically stable than arctan
    # NaN inputs will produce NaN outputs
    z_angle_radians = np.arctan2(az, horizontal_magnitude)

    # Convert to degrees
    return np.degrees(z_angle_radians)


def calculate_z_angle_from_dataframe(
    df: pd.DataFrame,
    ax_col: str = "AXIS_X",
    ay_col: str = "AXIS_Y",
    az_col: str = "AXIS_Z",
) -> pd.DataFrame:
    """
    Calculate z-angle from a DataFrame with tri-axial acceleration columns.

    Adds a new column 'z_angle' to the DataFrame containing the calculated
    z-angle in degrees for each row.

    Args:
        df: DataFrame with acceleration columns
        ax_col: Name of X-axis acceleration column (default: "AXIS_X")
        ay_col: Name of Y-axis acceleration column (default: "AXIS_Y")
        az_col: Name of Z-axis acceleration column (default: "AXIS_Z")

    Returns:
        DataFrame with added 'z_angle' column

    Raises:
        ValueError: If required columns are missing

    Example:
        >>> import pandas as pd
        >>> df = pd.DataFrame({
        ...     'AXIS_X': [0.1, 0.0, -0.1],
        ...     'AXIS_Y': [0.2, 0.0, -0.2],
        ...     'AXIS_Z': [0.9, 1.0, 0.9],
        ... })
        >>> df = calculate_z_angle_from_dataframe(df)
        >>> df['z_angle']
        0    76.3
        1    90.0
        2    76.3
        Name: z_angle, dtype: float64

    """
    # Validate required columns exist
    required_cols = [ax_col, ay_col, az_col]
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        msg = f"DataFrame missing required columns: {missing_cols}"
        raise ValueError(msg)

    # Extract acceleration arrays
    ax = df[ax_col].to_numpy(dtype=np.float64)
    ay = df[ay_col].to_numpy(dtype=np.float64)
    az = df[az_col].to_numpy(dtype=np.float64)

    # Calculate z-angle
    z_angle = calculate_z_angle_from_arrays(ax, ay, az)

    # Add to DataFrame
    result_df = df.copy()
    result_df["z_angle"] = z_angle

    return result_df


def resample_to_epochs(
    df: pd.DataFrame,
    timestamp_col: str,
    value_col: str,
    epoch_seconds: int,
    aggregation: str = "median",
) -> pd.DataFrame:
    """
    Resample high-frequency data to epoch-level aggregates.

    This is used to convert raw accelerometer samples to epoch-level z-angles
    for the van Hees algorithms.

    Args:
        df: DataFrame with timestamp and value columns
        timestamp_col: Name of timestamp column
        value_col: Name of value column to aggregate
        epoch_seconds: Epoch length in seconds (e.g., 5 for 5-second epochs)
        aggregation: Aggregation method - "median", "mean", "first", "last"

    Returns:
        DataFrame with resampled data at epoch resolution

    Raises:
        ValueError: If invalid aggregation method or columns missing

    Example:
        >>> import pandas as pd
        >>> df = pd.DataFrame({
        ...     'timestamp': pd.date_range('2024-01-01', periods=300, freq='1s'),
        ...     'z_angle': np.random.randn(300) + 45,
        ... })
        >>> epoch_df = resample_to_epochs(df, 'timestamp', 'z_angle', 5, 'median')
        >>> len(epoch_df)
        60

    """
    # Validate inputs
    if timestamp_col not in df.columns:
        msg = f"Timestamp column '{timestamp_col}' not found in DataFrame"
        raise ValueError(msg)

    if value_col not in df.columns:
        msg = f"Value column '{value_col}' not found in DataFrame"
        raise ValueError(msg)

    valid_aggregations = {"median", "mean", "first", "last"}
    if aggregation not in valid_aggregations:
        msg = f"Invalid aggregation '{aggregation}'. Must be one of: {valid_aggregations}"
        raise ValueError(msg)

    if epoch_seconds <= 0:
        msg = f"epoch_seconds must be positive, got {epoch_seconds}"
        raise ValueError(msg)

    # Ensure timestamp column is datetime
    if not pd.api.types.is_datetime64_any_dtype(df[timestamp_col]):
        df = df.copy()
        df[timestamp_col] = pd.to_datetime(df[timestamp_col])

    # Set timestamp as index for resampling
    df_indexed = df.set_index(timestamp_col)

    # Resample to epochs
    resampling_rule = f"{epoch_seconds}s"
    if aggregation == "median":
        resampled = df_indexed[value_col].resample(resampling_rule).median()
    elif aggregation == "mean":
        resampled = df_indexed[value_col].resample(resampling_rule).mean()
    elif aggregation == "first":
        resampled = df_indexed[value_col].resample(resampling_rule).first()
    elif aggregation == "last":
        resampled = df_indexed[value_col].resample(resampling_rule).last()
    else:
        # Default to median if invalid aggregation method specified
        resampled = df_indexed[value_col].resample(resampling_rule).median()

    # Reset index to get timestamp as column
    result_df = resampled.reset_index()
    result_df.columns = [timestamp_col, value_col]

    # Remove any NaN values (from empty epochs)
    return result_df.dropna()


def calculate_z_angle_change(
    z_angles: np.ndarray,
) -> np.ndarray:
    """
    Calculate absolute change in z-angle between consecutive epochs.

    This is used in the van Hees algorithms to detect movement. Large changes
    in z-angle indicate arm movement (wake), while small changes indicate
    stillness (sleep).

    Args:
        z_angles: Array of z-angle values in degrees

    Returns:
        Array of absolute z-angle changes (length = len(z_angles) - 1)

    Example:
        >>> z_angles = np.array([45.0, 46.0, 48.0, 45.5])
        >>> changes = calculate_z_angle_change(z_angles)
        >>> changes
        array([1.0, 2.0, 2.5])

    """
    if len(z_angles) < 2:
        msg = "Need at least 2 z-angle values to calculate change"
        raise ValueError(msg)

    # Calculate absolute difference between consecutive values
    return np.abs(np.diff(z_angles))


def calculate_rolling_median(
    values: np.ndarray,
    window_size: int,
) -> np.ndarray:
    """
    Calculate rolling median over a window.

    This is used in HDCZA to smooth the z-angle change signal.

    Args:
        values: Array of values
        window_size: Window size for rolling median

    Returns:
        Array of rolling median values (same length as input, padded with NaN at edges)

    Example:
        >>> values = np.array([1.0, 5.0, 2.0, 8.0, 3.0])
        >>> rolling_med = calculate_rolling_median(values, window_size=3)
        >>> rolling_med
        array([nan, 2.0, 5.0, 3.0, nan])

    """
    if window_size <= 0:
        msg = f"window_size must be positive, got {window_size}"
        raise ValueError(msg)

    if window_size > len(values):
        msg = f"window_size ({window_size}) cannot be larger than array length ({len(values)})"
        raise ValueError(msg)

    # Use pandas for efficient rolling median calculation
    import pandas as pd

    series = pd.Series(values)
    rolling_median = series.rolling(window=window_size, center=True).median()

    return rolling_median.to_numpy()


def split_into_noon_to_noon_days(
    df: pd.DataFrame,
    timestamp_col: str = "timestamp",
) -> list[pd.DataFrame]:
    """
    Split a multi-day recording into noon-to-noon segments.

    HDCZA uses noon-to-noon days to ensure complete nights are captured in
    a single analysis window.

    Args:
        df: DataFrame with timestamp column
        timestamp_col: Name of timestamp column

    Returns:
        List of DataFrames, one per noon-to-noon day

    Example:
        >>> import pandas as pd
        >>> df = pd.DataFrame({
        ...     'timestamp': pd.date_range('2024-01-01 08:00', periods=72, freq='1h'),
        ...     'value': range(72),
        ... })
        >>> days = split_into_noon_to_noon_days(df, 'timestamp')
        >>> len(days)
        3

    """
    if timestamp_col not in df.columns:
        msg = f"Timestamp column '{timestamp_col}' not found in DataFrame"
        raise ValueError(msg)

    # Ensure timestamp column is datetime
    df = df.copy()
    if not pd.api.types.is_datetime64_any_dtype(df[timestamp_col]):
        df[timestamp_col] = pd.to_datetime(df[timestamp_col])

    # Add a column for noon-to-noon day assignment
    # Each day runs from 12:00 (noon) to 11:59:59 next day
    timestamps = df[timestamp_col]

    # Shift timestamps back by 12 hours to align noon with midnight
    shifted = timestamps - pd.Timedelta(hours=12)

    # Get date component (this groups noon-to-noon periods)
    day_labels = shifted.dt.date

    # Split into separate DataFrames by day
    day_segments = []
    for day_label in day_labels.unique():
        day_mask = day_labels == day_label
        day_df = df[day_mask].copy().reset_index(drop=True)
        day_segments.append(day_df)

    return day_segments


def validate_raw_accelerometer_data(
    df: pd.DataFrame,
    timestamp_col: str = "timestamp",
    ax_col: str = "AXIS_X",
    ay_col: str = "AXIS_Y",
    az_col: str = "AXIS_Z",
) -> tuple[bool, list[str]]:
    """
    Validate that DataFrame contains valid raw accelerometer data.

    Checks for:
    - Required columns exist
    - Columns are correct data types
    - Acceleration values are within reasonable range
    - No excessive missing data

    Args:
        df: DataFrame to validate
        timestamp_col: Name of timestamp column
        ax_col: Name of X-axis column
        ay_col: Name of Y-axis column
        az_col: Name of Z-axis column

    Returns:
        Tuple of (is_valid, list of error messages)

    """
    errors = []

    # Check required columns exist
    required_cols = [timestamp_col, ax_col, ay_col, az_col]
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        errors.append(f"Missing required columns: {missing_cols}")
        return False, errors

    # Check timestamp is datetime
    if not pd.api.types.is_datetime64_any_dtype(df[timestamp_col]):
        errors.append(f"Timestamp column '{timestamp_col}' must be datetime type")

    # Check acceleration columns are numeric
    for col in [ax_col, ay_col, az_col]:
        if not pd.api.types.is_numeric_dtype(df[col]):
            errors.append(f"Acceleration column '{col}' must be numeric type")

    # Check for reasonable acceleration values (+/-20g is extreme but possible)
    for col in [ax_col, ay_col, az_col]:
        if col in df.columns and pd.api.types.is_numeric_dtype(df[col]):
            max_val = df[col].abs().max()
            if max_val > 20:
                errors.append(f"Acceleration column '{col}' has unreasonable values (max: {max_val:.1f}g)")

    # Check for excessive missing data
    for col in required_cols:
        if col in df.columns:
            missing_pct = df[col].isna().sum() / len(df) * 100
            if missing_pct > 50:
                errors.append(f"Column '{col}' has {missing_pct:.1f}% missing data (>50% threshold)")

    # Check minimum data length
    if len(df) < 100:
        errors.append(f"Insufficient data: only {len(df)} samples (need at least 100)")

    return len(errors) == 0, errors
