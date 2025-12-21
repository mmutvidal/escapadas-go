import subprocess
import sys

def run(cmd):
    print(f"\n▶ {cmd}")
    result = subprocess.run(
        cmd,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )
    print(result.stdout)
    return result.returncode, result.stdout


def require_admin():
    try:
        import ctypes
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False


if not require_admin():
    print("❌ Este script debe ejecutarse como ADMINISTRADOR.")
    print("👉 Abre cmd o PowerShell como administrador y vuelve a ejecutarlo.")
    sys.exit(1)


print("🔐 Configurando OpenSSH Server en Windows...")


# 1️⃣ Comprobar si OpenSSH Server está instalado
code, out = run(
    'dism /online /Get-Capabilities | findstr OpenSSH.Server'
)

if "NotPresent" in out:
    print("📦 OpenSSH Server no está instalado. Instalando...")
    run(
        'dism /online /Add-Capability /CapabilityName:OpenSSH.Server~~~~0.0.1.0'
    )
else:
    print("✅ OpenSSH Server ya está instalado.")


# 2️⃣ Arrancar servicio sshd
run('sc start sshd')

# 3️⃣ Configurar inicio automático
run('sc config sshd start= auto')

# 4️⃣ Abrir puerto 22 en firewall
run(
    'netsh advfirewall firewall add rule '
    'name="OpenSSH Server" '
    'dir=in action=allow protocol=TCP localport=22'
)

# 5️⃣ Verificar que escucha en 22
run('netstat -an | findstr :22')

print("\n🎉 SSH configurado.")
print("👉 Prueba ahora: ssh TU_USUARIO@localhost")