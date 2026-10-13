import { useState, type FormEvent } from 'react';
import { useLocation, useNavigate } from 'react-router';
import { FormattedMessage, useIntl } from 'react-intl';
import Alert from '@mui/material/Alert';
import Button from '@mui/material/Button';
import Stack from '@mui/material/Stack';
import TextField from '@mui/material/TextField';

import { useAuth } from 'data/auth';
import AuthLayout from 'layout/Auth';

export default function LoginPage() {
  const intl = useIntl();
  const navigate = useNavigate();
  const location = useLocation();
  const { login } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setError('');
    setBusy(true);
    try {
      const user = await login(email.trim().toLowerCase(), password);
      const from = (location.state as { from?: string } | null)?.from;
      navigate(user.must_change_password ? '/change-password' : from || '/chat', { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : intl.formatMessage({ id: 'login.error' }));
    } finally {
      setBusy(false);
    }
  };

  return (
    <AuthLayout title={<FormattedMessage id="login.title" />} subtitle={<FormattedMessage id="login.subtitle" />}>
      <Stack component="form" onSubmit={submit} sx={{ gap: 2 }} noValidate>
        {error && <Alert severity="error">{error}</Alert>}
        <TextField
          label={intl.formatMessage({ id: 'login.email' })}
          type="email"
          autoComplete="username"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
          autoFocus
          fullWidth
        />
        <TextField
          label={intl.formatMessage({ id: 'login.password' })}
          type="password"
          autoComplete="current-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
          fullWidth
        />
        <Button type="submit" variant="contained" size="large" disabled={busy || !email || !password}>
          <FormattedMessage id={busy ? 'login.submitting' : 'login.submit'} />
        </Button>
      </Stack>
    </AuthLayout>
  );
}
