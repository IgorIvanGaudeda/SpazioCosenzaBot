#!/usr/bin/env python3

from telegram.ext import Updater, CommandHandler
from telegram.ext import MessageHandler, Filters
import telegram
import requests
import re
import logging
from selenium import webdriver
from selenium.webdriver import Chrome
from selenium.webdriver.common.keys import Keys
import time
import random
from random import sample
from datetime import datetime, timedelta, timezone
import cx_Oracle as cx
from enum import Enum, auto
import configparser
import argparse

# define a few important global variables
dUserValidationInProgress = dict()
dUserValidationApartment = dict()
dUserValidationBlock = dict()
dUserValidationGarage = dict()
dApartmentsPerBlock = dict()
dBlockLords = dict()

tStartWaterInterruption = []
uInterruptionDurationHours = []
uSupplyDurationHours = []

user = []
key = []
database = []


class VerificationStates(Enum):
    NOTSTARTED = 0
    BLOCKSELECT = auto()
    APTSELECT = auto()
    LORDSELECT = auto()
    GARAGESELECT = auto()
    CONFIRM = auto()
    FINISHED = auto()


def start(update, context):
    context.bot.send_message(chat_id=update.effective_chat.id,
                             text="Olá " + update.message.from_user.first_name +
                                  "! Sou o robô do Spazio Cosenza. Estou aqui para te ajudar. " +
                                  "Para iniciar sua verificação, envie o comando /verificar para mim. " +
                                  "Para saber quais comandos eu entendo, envie /ajuda.")


def get_url():
    contents = requests.get('https://random.dog/woof.json').json()
    url = contents['url']
    return url


def get_image_url():
    allowed_extension = ['jpg', 'jpeg', 'png']
    file_extension = ''
    while file_extension not in allowed_extension:
        url = get_url()
        file_extension = re.search("([^.]*)$", url).group(1).lower()
    return url


def verification(update, context):

    if update.effective_chat.id == -1001439415702:
        reply_markup = telegram.ReplyKeyboardRemove()
        context.bot.send_message(chat_id=update.effective_chat.id,
                                 text="Este comando só pode ser executado em chat privado.",
                                 reply_markup=reply_markup)
        return

    reply_markup = telegram.ReplyKeyboardRemove()
    context.bot.send_message(chat_id=update.effective_chat.id, text="Estou buscando o seu usuário...",
                             reply_markup=reply_markup)

    if update.message.from_user.id in dUserValidationInProgress.keys():
        if dUserValidationInProgress[update.message.from_user.id] == VerificationStates.FINISHED:
            context.bot.send_message(chat_id=update.effective_chat.id,
                                     text="Você já foi verificado! Caso queria desvincular seu usuário, me envie " +
                                          "o comando /sair. Você poderá fazer o processo novamente caso deseje.")
            return
        else:
            context.bot.send_message(chat_id=update.effective_chat.id,
                                     text="Ok, vamos recomeçar sua verificação!")
    else:
        context.bot.send_message(chat_id=update.effective_chat.id,
                                 text="Ok, vamos começar sua verificação!")

    dUserValidationInProgress[update.message.from_user.id] = VerificationStates.BLOCKSELECT

    custom_keyboard = [['01', '02', '03', '04', '05'], ['06', '07', '08', '09', '10'],
                       ['11', '12', '13', '14', '15'], ['16', '17', '18', '19', '20'],
                       ['21', '22', '23', '24', '25'], ['26', '27', '28', '29', '30']]

    reply_markup = telegram.replykeyboardmarkup.ReplyKeyboardMarkup(custom_keyboard)
    context.bot.send_message(chat_id=update.effective_chat.id, text="Selecione seu bloco", reply_markup=reply_markup)


def echo(update, context):

    if dUserValidationInProgress[update.message.from_user.id] == VerificationStates.BLOCKSELECT:
        if int(update.message.text) not in range(1, 30):
            reply_markup = telegram.ReplyKeyboardRemove()
            context.bot.send_message(chat_id=update.effective_chat.id, text='Desculpe, não encontrei este bloco!',
                                     reply_markup=reply_markup)
            dUserValidationInProgress[update.message.from_user.id] = VerificationStates.NOTSTARTED
            return

        context.bot.send_message(chat_id=update.effective_chat.id, text='Ok, seu bloco é ' + update.message.text)
        custom_keyboard = dApartmentsPerBlock[int(update.message.text)]
        dUserValidationBlock[update.message.from_user.id] = update.message.text
        dUserValidationInProgress[update.message.from_user.id] = VerificationStates.APTSELECT
        reply_markup = telegram.replykeyboardmarkup.ReplyKeyboardMarkup(custom_keyboard)
        context.bot.send_message(chat_id=update.effective_chat.id, text="Selecione seu Apartamento",
                                 reply_markup=reply_markup)

    elif dUserValidationInProgress[update.message.from_user.id] == VerificationStates.APTSELECT:
        flatlist = []
        for elem in dApartmentsPerBlock[int(dUserValidationBlock[update.message.from_user.id])]:
            flatlist.extend(elem)

        if update.message.text not in flatlist:
            reply_markup = telegram.ReplyKeyboardRemove()
            context.bot.send_message(chat_id=update.effective_chat.id, text='Desculpe, não encontrei este apartamento!',
                                     reply_markup=reply_markup)
            dUserValidationInProgress[update.message.from_user.id] = VerificationStates.NOTSTARTED
            return

        context.bot.send_message(chat_id=update.effective_chat.id, text='Ok, seu apartamento é ' + update.message.text)
        dUserValidationApartment[update.message.from_user.id] = update.message.text

        # find garage by block and apt, asks for answer
        con = cx.connect(user, key, database)
        cur = con.cursor()

        cur.execute("SELECT garage FROM GARAGES WHERE apartment = {0} and block = {1}".format(
            dUserValidationApartment[update.message.from_user.id],
            dUserValidationBlock[update.message.from_user.id]))

        garage = cur.fetchone()
        if garage[0]:
            # asks if add
            dUserValidationInProgress[update.message.from_user.id] = VerificationStates.GARAGESELECT
            custom_keyboard = [['Sim', 'Não']]
            reply_markup = telegram.replykeyboardmarkup.ReplyKeyboardMarkup(custom_keyboard)
            context.bot.send_message(chat_id=update.effective_chat.id,
                                     text="Gostaria de adicionar a sua garagem " +
                                          str(garage[0]) +
                                          " ao seu usuário? Assim você poderá receber avisos sobre a sua vaga.",
                                     reply_markup=reply_markup)
            dUserValidationGarage[update.message.from_user.id] = garage[0]
        else:
            dUserValidationInProgress[update.message.from_user.id] = VerificationStates.LORDSELECT
            # start next one
            block = int(dUserValidationBlock[update.message.from_user.id])

            blocks = range(1, 30)
            subset = sample(blocks, 4)
            if block not in subset:
                subset[3] = block
            random.shuffle(subset)
            custom_keyboard = [[dBlockLords[subset[0]]],
                               [dBlockLords[subset[1]]],
                               [dBlockLords[subset[2]]],
                               [dBlockLords[subset[3]]]]

            dUserValidationInProgress[update.message.from_user.id] = VerificationStates.LORDSELECT
            reply_markup = telegram.replykeyboardmarkup.ReplyKeyboardMarkup(custom_keyboard)
            context.bot.send_message(chat_id=update.effective_chat.id,
                                     text="Selecione seu Síndico de bloco. Se você " +
                                          "não souber, procure no app Vida de Síndico.",
                                     reply_markup=reply_markup)
        cur.close()
        con.close()

    elif dUserValidationInProgress[update.message.from_user.id] == VerificationStates.GARAGESELECT:
        reply_markup = telegram.ReplyKeyboardRemove()
        if update.message.text == 'Sim':
            context.bot.send_message(chat_id=update.effective_chat.id,
                                     text="Ok, A vaga " +
                                          str(dUserValidationGarage[update.message.from_user.id]) +
                                          " será relacionada ao seu usuário.",
                                     reply_markup=reply_markup)
        else:
            context.bot.send_message(chat_id=update.effective_chat.id,
                                     text="Ok, A vaga " +
                                          str(dUserValidationGarage[update.message.from_user.id]) +
                                          " não será relacionada ao seu usuário, mas você pode fazer isso no futuro.",
                                     reply_markup=reply_markup)
            dUserValidationGarage.pop(update.message.from_user.id)

        # start next one
        block = int(dUserValidationBlock[update.message.from_user.id])

        blocks = range(1, 30)
        subset = sample(blocks, 4)
        if block not in subset:
            subset[3] = block
        random.shuffle(subset)
        custom_keyboard = [[dBlockLords[subset[0]]],
                           [dBlockLords[subset[1]]],
                           [dBlockLords[subset[2]]],
                           [dBlockLords[subset[3]]]]

        dUserValidationInProgress[update.message.from_user.id] = VerificationStates.LORDSELECT
        reply_markup = telegram.replykeyboardmarkup.ReplyKeyboardMarkup(custom_keyboard)
        context.bot.send_message(chat_id=update.effective_chat.id,
                                 text="Selecione seu Síndico de bloco. Se você " +
                                      "não souber, procure no app Vida de Síndico.",
                                 reply_markup=reply_markup)

    elif dUserValidationInProgress[update.message.from_user.id] == VerificationStates.LORDSELECT:
        dUserValidationInProgress[update.message.from_user.id] = VerificationStates.CONFIRM
        custom_keyboard = [['Sim', 'Não']]
        if dBlockLords[int(dUserValidationBlock[update.message.from_user.id])] == update.message.text:
            reply_markup = telegram.replykeyboardmarkup.ReplyKeyboardMarkup(custom_keyboard)
            garage_string = str(dUserValidationGarage[update.message.from_user.id]) if update.message.from_user.id in \
                                                                                       dUserValidationGarage else "ND"

            context.bot.send_message(chat_id=update.effective_chat.id,
                                     text="Bloco " + str(dUserValidationBlock[update.message.from_user.id]) +
                                          " Apt. " + str(dUserValidationApartment[update.message.from_user.id]) +
                                          " Garagem " + garage_string +
                                          " Síndico(a) do bloco " + update.message.text +
                                          ". Essas informações estão corretas?",
                                     reply_markup=reply_markup)
        else:
            reply_markup = telegram.ReplyKeyboardRemove()
            context.bot.send_message(chat_id=update.effective_chat.id,
                                     text="Não foi possível completar, por favor, verifique as informações e tente " +
                                          "novamente.",
                                     reply_markup=reply_markup)
            dUserValidationInProgress[update.message.from_user.id] = VerificationStates.NOTSTARTED

    elif dUserValidationInProgress[update.message.from_user.id] == VerificationStates.CONFIRM:
        if update.message.text == 'Sim':
            reply_markup = telegram.ReplyKeyboardRemove()
            garage_string = str(dUserValidationGarage[update.message.from_user.id]) if update.message.from_user.id in \
                                                                                       dUserValidationGarage else "0"
            print(update.message.from_user.id)
            con = cx.connect(user, key, database)
            cur = con.cursor()
            sql = 'INSERT INTO DATADB VALUES (:apt, :garage, :name, :verified, :block, :userid)'
            cur.execute(sql, apt=dUserValidationApartment[update.message.from_user.id],
                        garage=garage_string,
                        name=update.message.from_user.first_name,
                        verified=1,
                        block=dUserValidationBlock[update.message.from_user.id],
                        userid=int(update.message.from_user.id))
            con.commit()
            cur.close()
            con.close()

            dUserValidationInProgress[update.message.from_user.id] = VerificationStates.FINISHED

            context.bot.send_message(chat_id=update.effective_chat.id,
                                     text="Verificação concluída! Agora você tem acesso a todos os meus comandos. " +
                                          "Para saber mais, envie /ajuda!",
                                     reply_markup=reply_markup)

        elif update.message.text == 'Não':
            reply_markup = telegram.ReplyKeyboardRemove()
            context.bot.send_message(chat_id=update.effective_chat.id,
                                     text="Sem problemas. Envie o comando de verificação para reiniciar o processo!",
                                     reply_markup=reply_markup)
            dUserValidationInProgress[update.message.from_user.id] = 0
        else:
            reply_markup = telegram.ReplyKeyboardRemove()
            context.bot.send_message(chat_id=update.effective_chat.id,
                                     text="Desculpe, não entendi. Envie o comando de verificação para reiniciar o " +
                                          "processo!",
                                     reply_markup=reply_markup)
            dUserValidationInProgress[update.message.from_user.id] = 0


def leave(update, context):

    if update.effective_chat.id == -1001439415702:
        reply_markup = telegram.ReplyKeyboardRemove()
        context.bot.send_message(chat_id=update.effective_chat.id,
                                 text="Este comando só pode ser executado em chat privado.",
                                 reply_markup=reply_markup)
        return

    print("DELETE FROM DATADB WHERE telegram_user_id = {0};".format(update.message.from_user.id))

    print(update.message.from_user.id)
    con = cx.connect(user, key, database)
    cur = con.cursor()
    sql = 'DELETE FROM DATADB WHERE telegram_user_id = :userid'
    cur.execute(sql, userid=int(update.message.from_user.id))

    dUserValidationInProgress[update.message.from_user.id] = 0
    con.commit()
    cur.close()
    con.close()

    reply_markup = telegram.ReplyKeyboardRemove()
    context.bot.send_message(chat_id=update.effective_chat.id,
                             text="Ok" + update.message.from_user.first_name +
                             ". Suas informações foram apagadas. Caso queira voltar a usar o bot, " +
                             "faça a verificação novamente através do comando /verificar",
                             reply_markup=reply_markup)


def garage(update, context):
    context.bot.send_message(chat_id=update.effective_chat.id,
                             text="Desculpe, esse comando ainda não foi programado!")
    # TODO: implement command
    #   the user can set his own garage and receive alerts


def warn(update, context):
    context.bot.send_message(chat_id=update.effective_chat.id,
                             text="Desculpe, esse comando ainda não foi programado!")
    # TODO: implement command
    #   the user can send a warning for an apartment or garage and a message


def emergency(update, context):
    context.bot.send_message(chat_id=update.effective_chat.id,
                             text="Desculpe, esse comando ainda não foi programado!")
    # TODO: implement command
    #   the user can sent an emergency message for all verified users
    #   users will receive this message with block/apt


def last_announcement(update, context):
    context.bot.send_message(chat_id=update.effective_chat.id,
                             text="Desculpe, esse comando ainda não foi programado!")
    # TODO: implement command
    #   retrieve last announcement from adm and sent to user

    # # Using Chrome to access web
    # driver = Chrome()
    # # Open the website
    # driver.get('https://vidadesindico.com.br/area-restrita/')
    #
    # context.bot.send_message(chat_id=update.effective_chat.id, text="Fim")


def self_help(update, context):
    print(update.effective_chat.id)
    reply_markup = telegram.ReplyKeyboardRemove()
    context.bot.send_message(chat_id=update.effective_chat.id,
                             text="Para conversar comigo, você precisa utilizar algum dos comandos a seguir:\n" +
                                  "/start: inicia uma conversa comigo.\n"
                                  "/verificar: verifica que você é um morador e dá acesso a mais comandos.\n" +
                                  "/sair: exclui seus dados de verificação.\n" +
                                  "/temagua: verifica se o abastecimento da SANEPAR está interrompido ou não.\n" +
                                  "/ajuda: informa os comandos disponíveis.\n",
                             reply_markup=reply_markup)


def water_supply(update, context):

    now = datetime.now()
    delta = now - tStartWaterInterruption
    hours = delta.total_seconds()/3600
    elapsed = hours % (uInterruptionDurationHours + uSupplyDurationHours)
    if elapsed <= uInterruptionDurationHours:
        context.bot.send_message(chat_id=update.effective_chat.id,
                                 text=update.message.from_user.first_name +
                                 ", o abastecimento de água está interrompido! Economize!\n" +
                                 "O abastecimento deve voltar em aproximadamente " +
                                 str(round(uInterruptionDurationHours - elapsed, 1)) + "h.")
    else:
        context.bot.send_message(chat_id=update.effective_chat.id,
                                 text=update.message.from_user.first_name +
                                 ", o abastecimento de água está normalizado, mas continue economizando!\n" +
                                 "O abastecimento deve ser interompido em aproximadamente " +
                                 str(round(uInterruptionDurationHours + uSupplyDurationHours - elapsed, 1)) + "h.")


def unknown(update, context):
    context.bot.send_message(chat_id=update.effective_chat.id,
                             text="Desculpe " + update.message.from_user.first_name + ", não entendi este comando." +
                                  "Para saber quais comandos eu respondo, envie /ajuda.")


def main():

    parser = argparse.ArgumentParser()
    parser.add_argument("config", help="config file for DB login")
    args = parser.parse_args()

    config = configparser.ConfigParser()
    config.read(args.config)

    global user
    user = config['DEFAULT']['User']
    global key
    key = config['DEFAULT']['Key']
    global database
    database = config['DEFAULT']['DBName']

    print("user", user)
    print("key", key)
    print("dbname", database)

    global tStartWaterInterruption
    tStartWaterInterruption = datetime(2020, 10, 5, 19, 0, 0)  # 3 horus due to timezone
    global uInterruptionDurationHours
    uInterruptionDurationHours = 36
    global uSupplyDurationHours
    uSupplyDurationHours = 36

    blocos6apt = [3, 4, 5, 22, 23, 24, 27, 28, 29, 30]

    for bloco in range(1, 31, 1):
        if bloco in blocos6apt:
            dApartmentsPerBlock[bloco] = [['101', '102', '103', '104', '105', '106'],
                                          ['201', '202', '203', '204', '205', '206'],
                                          ['301', '302', '303', '304', '305', '306'],
                                          ['401', '402', '403', '404', '405', '406'],
                                          ['501', '502', '503', '504', '505', '506'],
                                          ['601', '602', '603', '604', '605', '606']]
        else:
            dApartmentsPerBlock[bloco] = [['101', '102', '103', '104'],
                                          ['201', '202', '203', '204'],
                                          ['301', '302', '303', '304'],
                                          ['401', '402', '403', '404'],
                                          ['501', '502', '503', '504'],
                                          ['601', '602', '603', '604']]


    # restore verified users
    con = cx.connect(user, key, database)
    cur = con.cursor()
    cur.execute("SELECT telegram_user_id FROM DATADB WHERE verified = 1")
    for telegram_user_id in cur:
        dUserValidationInProgress[telegram_user_id[0]] = VerificationStates.FINISHED
        print("Verified ID: {0}", telegram_user_id[0])
    cur.close()
    con.close()

    dBlockLords[1] = 'Jose Roberto Alves Fernandes'
    dBlockLords[2] = 'Wellington Nunes'
    dBlockLords[3] = 'Ernesto Linhares da Silva'
    dBlockLords[4] = 'Marcia Helena Rodrigues da Silva'
    dBlockLords[5] = 'Leandro Lacerda Da Silva'
    dBlockLords[6] = 'Eder Leite'
    dBlockLords[7] = 'Andre Brum'
    dBlockLords[8] = 'Jessica Sambulski'
    dBlockLords[9] = 'Andre Guiguer Da Costa'
    dBlockLords[10] = 'Leticia Correa De Oliveira'
    dBlockLords[11] = 'Wellington Cesar Soares'
    dBlockLords[12] = 'Grazielly Cristine Ferreira'
    dBlockLords[13] = 'Jeniffer Rossi Bezerra'
    dBlockLords[14] = 'Christiane Regina Bittencourt'
    dBlockLords[15] = 'Caroline Thais Pinheiro'
    dBlockLords[16] = 'Ketlin Keslim Pereira'
    dBlockLords[17] = 'Zamily Bernadethe Duarte Niedzievski'
    dBlockLords[18] = 'Rodrigo Dias De Melo'
    dBlockLords[19] = 'Elton Ulisses Arimateas Navakoski'
    dBlockLords[20] = 'Victor Hugo Ribeiro F. dos Santos'
    dBlockLords[21] = 'Luis Guilherme Panceri'
    dBlockLords[22] = 'Johanna Herrera Velazquez'
    dBlockLords[23] = 'Mariley Piazza Dias Zanol'
    dBlockLords[24] = 'Daniele Lucio Silva'
    dBlockLords[25] = 'Claudineia Aparecida Da Silva'
    dBlockLords[26] = 'Nenhum'
    dBlockLords[27] = 'Nenhum'
    dBlockLords[28] = 'Marcos Antonio Ito'
    dBlockLords[29] = 'Christian Semenoff Grandke'
    dBlockLords[30] = 'Marcelo Rodrigues Bueno'

    # initialize dispatcher
    updater = Updater('1375319606:AAG92HEzTOgu1ixQ1W5sADAtwOLNHY2WQJU', use_context=True)
    dispatcher = updater.dispatcher

    # initialize /start handler
    start_handler = CommandHandler('start', start)
    dispatcher.add_handler(start_handler)

    # initialize /verificar handler
    verification_handler = CommandHandler('verificar', verification)
    dispatcher.add_handler(verification_handler)

    # initialize /sair handler
    exit_handler = CommandHandler('sair', leave)
    dispatcher.add_handler(exit_handler)

    # initialize /garagem handler
    garage_handler = CommandHandler('garagem', garage)
    dispatcher.add_handler(garage_handler)

    # initialize /avisar handler
    warn_handler = CommandHandler('avisar', warn)
    dispatcher.add_handler(warn_handler)

    # initialize /emergencia handler
    emergency_handler = CommandHandler('emergencia', emergency)
    dispatcher.add_handler(emergency_handler)

    # initialize /ultimoavisoadm handler
    last_announcement_handler = CommandHandler('ultimoavisoadm', last_announcement)
    dispatcher.add_handler(last_announcement_handler)

    # initialize /temagua handler
    water_supply_handler = CommandHandler('temagua', water_supply)
    dispatcher.add_handler(water_supply_handler)

    # initialize /ajuda handler
    water_supply_handler = CommandHandler('ajuda', self_help)
    dispatcher.add_handler(water_supply_handler)

    # initialize echo handler
    echo_handler = MessageHandler(Filters.text & (~Filters.command), echo)
    dispatcher.add_handler(echo_handler)

    # initialize unknown command handler
    unknown_handler = MessageHandler(Filters.command, unknown)
    dispatcher.add_handler(unknown_handler)

    # start the dispatcher
    print("Starting polling")
    updater.start_polling()

    updater.idle()


if __name__ == '__main__':
    main()

