#
# Copyright 2018 Analytics Zoo Authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
import os
import shutil
import tempfile

import pytest

from zoo.automl.common.util import *
from zoo.automl.feature.time_sequence import *


class TestTimeSequenceFeature:

    def test_get_feature_list(self):
        dates = pd.date_range('1/1/2019', periods=8)
        values = np.random.randn(8)
        df = pd.DataFrame({"datetime": dates, "values": values})
        feat = TimeSequenceFeatureTransformer(dt_col="datetime", target_col="values", drop_missing=True)
        feature_list = feat.get_feature_list(df)
        assert set(feature_list) == {'IS_AWAKE(datetime)',
                                     'IS_BUSY_HOURS(datetime)',
                                     'HOUR(datetime)',
                                     'DAY(datetime)',
                                     'IS_WEEKEND(datetime)',
                                     'WEEKDAY(datetime)',
                                     'MONTH(datetime)'}

    def test_fit_transform(self):
        sample_num = 8
        past_seq_len = 2
        dates = pd.date_range('1/1/2019', periods=sample_num)
        values = np.random.randn(sample_num)
        df = pd.DataFrame({"datetime": dates, "values": values})
        config = {"selected_features": ['IS_AWAKE(datetime)', 'IS_BUSY_HOURS(datetime)', 'HOUR(datetime)'],
                  "past_seq_len": past_seq_len}
        feat = TimeSequenceFeatureTransformer(future_seq_len=1, dt_col="datetime",
                                              target_col="values", drop_missing=True)
        x, y = feat.fit_transform(df, **config)
        assert x.shape == (sample_num-past_seq_len, past_seq_len, 4)
        assert y.shape == (sample_num-past_seq_len, 1)
        assert np.mean(np.concatenate((x[0, :, 0], y[:, 0]), axis=None)) < 1e-5

    def test_fit_transform_input_datetime(self):
        # if the type of input datetime is not datetime64, raise an error
        dates = pd.date_range('1/1/2019', periods=8)
        values = np.random.randn(8)
        df = pd.DataFrame({"datetime": dates.strftime('%m/%d/%Y'), "values": values})
        config = {"selected_features": ['IS_AWAKE(datetime)', 'IS_BUSY_HOURS(datetime)', 'HOUR(datetime)'],
                  "past_seq_len": 2}
        feat = TimeSequenceFeatureTransformer(future_seq_len=1, dt_col="datetime",
                                              target_col="values", drop_missing=True)

        with pytest.raises(ValueError) as excinfo:
            feat.fit_transform(df, **config)
        assert 'np.datetime64' in str(excinfo.value)

        # if there is NaT in datetime, raise an error
        df.loc[1, "datetime"] = None
        with pytest.raises(ValueError, match=r".* datetime .*"):
            feat.fit_transform(df, **config)

        # if the last datetime is larger than current time, raise an error
        dates = pd.date_range('1/1/2119', periods=8)
        values = np.random.randn(8)
        df = pd.DataFrame({"datetime": dates, "values": values})
        config = {"selected_features": ['IS_AWAKE(datetime)', 'IS_BUSY_HOURS(datetime)', 'HOUR(datetime)'],
                  "past_seq_len": 2}
        feat = TimeSequenceFeatureTransformer(future_seq_len=1, dt_col="datetime",
                                              target_col="values", drop_missing=True)

        with pytest.raises(ValueError, match=r".* current .*"):
            feat.fit_transform(df, **config)

    def test_fit_transform_past_seq_len(self):
        # if the past_seq_len exceeds (sample_num - future_seq_len), raise an error
        sample_num = 8
        past_seq_len = 10
        dates = pd.date_range('1/1/2019', periods=sample_num)
        values = np.random.randn(sample_num)
        df = pd.DataFrame({"datetime": dates, "values": values})
        config = {"selected_features": ['IS_AWAKE(datetime)', 'IS_BUSY_HOURS(datetime)', 'HOUR(datetime)'],
                  "past_seq_len": past_seq_len}
        feat = TimeSequenceFeatureTransformer(future_seq_len=1, dt_col="datetime",
                                              target_col="values", drop_missing=True)
        with pytest.raises(ValueError, match=r".*past_seq_len.*"):
            x, y = feat.fit_transform(df, **config)

    def test_fit_transform_input_data(self):
        # if there is NaN in data other than datetime, drop the training sample.
        dates = pd.date_range('1/1/2019', periods=8)
        values = np.random.randn(8)
        df = pd.DataFrame({"datetime": dates, "values": values})
        df.loc[2, "values"] = None

        config = {"selected_features": ['IS_AWAKE(datetime)', 'IS_BUSY_HOURS(datetime)', 'HOUR(datetime)'],
                  "past_seq_len": 2}
        feat = TimeSequenceFeatureTransformer(future_seq_len=1, dt_col="datetime",
                                              target_col="values", drop_missing=True)

        x, y = feat.fit_transform(df, **config)
        # mask_x = [1, 0, 0, 1, 1, 1]
        # mask_y = [0, 1, 1, 1, 1, 1]
        # mask   = [0, 0, 0, 1, 1, 1]
        assert x.shape == (3, 2, 4)
        assert y.shape == (3, 1)

    def test_transform_train_true(self):
        dates = pd.date_range('1/1/2019', periods=16)
        values = np.random.randn(16)
        df = pd.DataFrame({"datetime": dates, "values": values})

        config = {"selected_features": ['IS_AWAKE(datetime)', 'IS_BUSY_HOURS(datetime)', 'HOUR(datetime)'],
                  "past_seq_len": 2}
        feat = TimeSequenceFeatureTransformer(future_seq_len=1, dt_col="datetime",
                                              target_col="values", drop_missing=True)

        feat.fit_transform(df[:10], **config)
        val_x, val_y = feat.transform(df[10:], is_train=True)
        assert val_x.shape == (4, 2, 4)
        assert val_y.shape == (4, 1)

    def test_transform_train_false(self):
        dates = pd.date_range('1/1/2019', periods=16)
        values = np.random.randn(16)
        df = pd.DataFrame({"datetime": dates, "values": values})

        config = {"selected_features": ['IS_AWAKE(datetime)', 'IS_BUSY_HOURS(datetime)', 'HOUR(datetime)'],
                  "past_seq_len": 2}
        feat = TimeSequenceFeatureTransformer(future_seq_len=1, dt_col="datetime",
                                              target_col="values", drop_missing=True)

        feat.fit_transform(df[:10], **config)
        test_x = feat.transform(df[10:], is_train=False)
        assert test_x.shape == (5, 2, 4)

    def test_save_restore(self):
        dates = pd.date_range('1/1/2019', periods=8)
        values = np.random.randn(8)
        df = pd.DataFrame({"dt": dates, "v": values})

        # config = {"selected_features": ['IS_AWAKE(datetime)', 'IS_BUSY_HOURS(datetime)', 'HOUR(datetime)'],
        #           "past_seq_len": 2}
        future_seq_len = 2
        dt_col = "dt"
        target_col = "v"
        drop_missing = True
        feat = TimeSequenceFeatureTransformer(future_seq_len=future_seq_len,
                                              dt_col=dt_col,
                                              target_col=target_col,
                                              drop_missing=drop_missing)

        feature_list = feat.get_feature_list(df)
        config = {"selected_features": feature_list,
                  "past_seq_len": 2
                  }

        train_x, train_y = feat.fit_transform(df, **config)

        dirname = tempfile.mkdtemp(prefix="automl_test_feature")
        try:
            save(dirname, feature_transformers=feat)
            new_ft = TimeSequenceFeatureTransformer()
            restore(dirname, feature_transformers=new_ft, config=config)

            assert new_ft.future_seq_len == future_seq_len
            assert new_ft.dt_col == dt_col
            assert new_ft.target_col == target_col
            assert new_ft.extra_features_col is None
            assert new_ft.drop_missing == drop_missing

            test_x = new_ft.transform(df[:-future_seq_len], is_train=False)

            assert np.array_equal(test_x, train_x)

        finally:
            shutil.rmtree(dirname)

    def test_post_processing_train(self):
        dates = pd.date_range('1/1/2019', periods=8)
        values = np.random.randn(8)
        dt_col = "datetime"
        value_col = "values"
        df = pd.DataFrame({dt_col: dates, value_col: values})

        past_seq_len = 2
        future_seq_len = 1
        config = {"selected_features": ['IS_AWAKE(datetime)', 'IS_BUSY_HOURS(datetime)', 'HOUR(datetime)'],
                  "past_seq_len": past_seq_len}
        feat = TimeSequenceFeatureTransformer(future_seq_len=future_seq_len, dt_col="datetime",
                                              target_col="values", drop_missing=True)

        train_x, train_y = feat.fit_transform(df, **config)
        y_unscale, y_unscale_1 = feat.post_processing(df, train_y, is_train=True)
        y_input = df[past_seq_len:][[value_col]].values
        assert np.allclose(y_unscale, y_unscale_1), "y_unscale is {}, y_unscale_1 is {}".format(y_unscale, y_unscale_1)
        assert np.array_equal(y_unscale, y_input), "y_unscale is {}, y_input is {}".format(y_unscale, y_input)

    def test_post_processing_test_1(self):
        dates = pd.date_range('1/1/2019', periods=8)
        values = np.random.randn(8)
        dt_col = "datetime"
        value_col = "values"
        df = pd.DataFrame({dt_col: dates, value_col: values})

        past_seq_len = 2
        future_seq_len = 1
        config = {"selected_features": ['IS_AWAKE(datetime)', 'IS_BUSY_HOURS(datetime)', 'HOUR(datetime)'],
                  "past_seq_len": past_seq_len}
        feat = TimeSequenceFeatureTransformer(future_seq_len=future_seq_len, dt_col="datetime",
                                              target_col="values", drop_missing=True)

        train_x, train_y = feat.fit_transform(df, **config)

        dirname = tempfile.mkdtemp(prefix="automl_test_feature_")
        try:
            save(dirname, feature_transformers=feat)
            new_ft = TimeSequenceFeatureTransformer()
            restore(dirname, feature_transformers=new_ft, config=config)

            test_df = df[:-future_seq_len]
            new_ft.transform(test_df, is_train=False)
            output_value_df = new_ft.post_processing(test_df, train_y, is_train=False)
            target_df = df[past_seq_len:].copy().reset_index(drop=True)

            assert output_value_df[dt_col].equals(target_df[dt_col])
            assert np.allclose(output_value_df[value_col].values, target_df[value_col].values)

        finally:
            shutil.rmtree(dirname)

    def test_post_processing_test_2(self):
        sample_num = 8
        dates = pd.date_range('1/1/2019', periods=sample_num)
        values = np.random.randn(sample_num)
        dt_col = "datetime"
        value_col = "values"
        df = pd.DataFrame({dt_col: dates, value_col: values})

        past_seq_len = 2
        future_seq_len = 2
        config = {"selected_features": ['IS_AWAKE(datetime)', 'IS_BUSY_HOURS(datetime)', 'HOUR(datetime)'],
                  "past_seq_len": past_seq_len}
        feat = TimeSequenceFeatureTransformer(future_seq_len=future_seq_len, dt_col="datetime",
                                              target_col="values", drop_missing=True)

        train_x, train_y = feat.fit_transform(df, **config)

        dirname = tempfile.mkdtemp(prefix="automl_test_feature_")
        try:
            save(dirname, feature_transformers=feat)
            new_ft = TimeSequenceFeatureTransformer()
            restore(dirname, feature_transformers=new_ft, config=config)

            test_df = df[:-future_seq_len]
            new_ft.transform(test_df, is_train=False)
            output_value_df = new_ft.post_processing(test_df, train_y, is_train=False)
            assert output_value_df.shape == (sample_num-past_seq_len-future_seq_len+1, future_seq_len + 1)

            columns = ["value_{}".format(i) for i in range(future_seq_len)]
            output_value = output_value_df[columns].values
            target_df = df[past_seq_len:].copy().reset_index(drop=True)
            target_value = feat._roll_test(target_df["values"], future_seq_len)

            assert output_value_df[dt_col].equals(target_df[:-future_seq_len+1][dt_col])
            assert np.allclose(output_value, target_value), \
                "output_value is {}, target_value is {}".format(output_value, target_value)
            # assert np.allclose(output_value_df[value_col].values, target_df[value_col].values)

        finally:
            shutil.rmtree(dirname)


if __name__ == '__main__':
    pytest.main([__file__])