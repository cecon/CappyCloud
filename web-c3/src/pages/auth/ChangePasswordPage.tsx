import { useState, type FormEvent } from 'react';
import { useNavigate } from 'react-router';
import { FormattedMessage, useIntl } from 'react-intl';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Stack from '@mui/material/Stack';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';

import { MainCard } from '@c3theme/ui';

import { changePasswordRequest, getToken } from 'data';
import { useAuth } from 'data/auth';
import AuthLayout from 'layout/Auth';
import { APP_DEFAULT_PATH } from 'config';

// Mesma regra do web/src/pages/ChangePasswordPage.tsx.
const MIN_LENGTH = 8;

export default function ChangePasswordPage() {
  const intl = useIntl();
  const navigate = useNavigate();
  const { state, setUser, logout } = useAuth();
  const [current, setCurrent] = useState('');
  const [next, setNext] = useState('');
  const [confirm, setConfirm] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const forced = state.status === 'ready' && state.user.must_change_password;

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setError('');
    if (next.length < MIN_LENGTH) {
      setError(intl.formatMessage({ id: 'password.tooShort' }, { min: MIN_LENGTH }));
      return;
    }
    if (next !== confirm) {
      setError(intl.formatMessage({ id: 'password.mismatch' }));
      return;
    }
    const token = getToken();
    if (!token) {
      logout();
      return;
    }
    setBusy(true);
    try {
      setUser(await changePasswordRequest(token, current, next));
      navigate(APP_DEFAULT_PATH, { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : intl.formatMessage({ id: 'password.error' }));
    } finally {
      setBusy(false);
    }
  };

  const form = (
    <Stack component="form" onSubmit={submit} sx={{ gap: 2 }} noValidate>
      {error && <Alert severity="error">{error}</Alert>}
      <TextField
        label={intl.formatMessage({ id: 'password.current' })}
        type="password"
        autoComplete="current-password"
        value={current}
        onChange={(e) => setCurrent(e.target.value)}
        required
        autoFocus
        fullWidth
      />
      <TextField
        label={intl.formatMessage({ id: 'password.new' })}
        type="password"
        autoComplete="new-password"
        value={next}
        onChange={(e) => setNext(e.target.value)}
        helperText={intl.formatMessage({ id: 'password.hint' }, { min: MIN_LENGTH })}
        required
        fullWidth
      />
      <TextField
        label={intl.formatMessage({ id: 'password.confirm' })}
        type="password"
        autoComplete="new-password"
        value={confirm}
        onChange={(e) => setConfirm(e.target.value)}
        required
        fullWidth
      />
      <Stack direction="row" sx={{ gap: 1, justifyContent: 'flex-end' }}>
        {!forced && (
          <Button onClick={() => navigate(-1)} disabled={busy}>
            <FormattedMessage id="common.cancel" />
          </Button>
        )}
        <Button type="submit" variant="contained" disabled={busy || !current || !next || !confirm}>
          <FormattedMessage id={busy ? 'common.saving' : 'password.submit'} />
        </Button>
      </Stack>
    </Stack>
  );

  // Troca obrigatória: tela própria, sem menu. Troca voluntária: dentro do layout, como no web/.
  if (forced) {
    return (
      <AuthLayout title={<FormattedMessage id="password.title" />} subtitle={<FormattedMessage id="password.forced" />}>
        {form}
      </AuthLayout>
    );
  }

  return (
    <Box sx={{ maxWidth: 480 }}>
      <MainCard title={<FormattedMessage id="password.title" />}>
        <Typography color="text.secondary" sx={{ mb: 2 }}>
          <FormattedMessage id="password.subtitle" />
        </Typography>
        {form}
      </MainCard>
    </Box>
  );
}
